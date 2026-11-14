import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import CounterEpoch, Device, DeviceCredential, Measurement, MonitoringSession, Participant, Sensor, SensorCapability, SessionDevice, TelemetryPacket


class TelemetryAPITests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.participant = Participant.objects.create(pseudonym="synthetic-api-001")
        self.session = MonitoringSession.objects.create(
            identifier="session-demo-001", participant=self.participant,
            started_at=self.now - timedelta(days=2),
        )
        self.other_session = MonitoringSession.objects.create(
            identifier="session-other-001", participant=self.participant,
            started_at=self.now - timedelta(days=2),
        )
        self.device = Device.objects.create(identifier="harness-sim-001", kind=Device.Kind.HARNESS, source=Device.Source.SIMULATED)
        self.other_device = Device.objects.create(identifier="harness-sim-002", kind=Device.Kind.HARNESS, source=Device.Source.SIMULATED)
        self.assignment = SessionDevice.objects.create(session=self.session, device=self.device, assigned_at=self.now - timedelta(days=2))
        self.sensor = Sensor.objects.create(identifier="hr-sim-001", device=self.device, channel="hr", profile_version="demo-1")
        SensorCapability.objects.create(sensor=self.sensor, metric="heart_rate", unit="bpm", enabled=True)
        self.dose_sensor = Sensor.objects.create(identifier="dose-sim-001", device=self.device, channel="dose")
        SensorCapability.objects.create(sensor=self.dose_sensor, metric="absorbed_dose_cumulative", unit="uGy", enabled=True)
        self.epoch = CounterEpoch.objects.create(assignment=self.assignment, sensor=self.dose_sensor, started_at=self.now - timedelta(days=2))
        self.reader = get_user_model().objects.create_user(username="reader", password="reader-password")
        self.stranger = get_user_model().objects.create_user(username="stranger", password="stranger-password")
        self.staff = get_user_model().objects.create_user(username="staff", password="staff-password", is_staff=True)
        self.session.authorized_users.add(self.reader)
        self.secret = "synthetic-test-device-secret"
        self.credential = DeviceCredential.objects.create(device=self.device, secret_hash=make_password(self.secret))
        self.device_client = APIClient()
        self.device_client.credentials(HTTP_AUTHORIZATION=f"Device {self.credential.pk}:{self.secret}")

    def packet(self, *, packet_id=None, observed_at=None, value="78.0", readings=None):
        return {
            "packet_id": str(packet_id or uuid.uuid4()),
            "device_id": self.device.identifier,
            "session_id": self.session.identifier,
            "observed_at": (observed_at or self.now).isoformat(),
            "source": "simulated",
            "readings": readings if readings is not None else [
                {"sensor_id": self.sensor.identifier, "metric": "heart_rate", "value": value, "unit": "bpm", "quality": "valid"}
            ],
        }

    def send(self, packets, client=None, version=1):
        return (client or self.device_client).post(
            "/api/v1/telemetry/batches/", {"schema_version": version, "packets": packets}, format="json"
        )

    def test_configuration_crud_is_staff_only(self):
        client = APIClient()
        client.force_authenticate(self.reader)
        self.assertEqual(client.get("/api/v1/config/participants/").status_code, 403)
        client.force_authenticate(self.staff)
        created = client.post("/api/v1/config/participants/", {"pseudonym": "synthetic-new"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        identifier = created.data["id"]
        self.assertEqual(client.patch(f"/api/v1/config/participants/{identifier}/", {"pseudonym": "synthetic-edited"}, format="json").status_code, 200)
        self.assertEqual(client.get(f"/api/v1/config/participants/{identifier}/").data["pseudonym"], "synthetic-edited")
        self.assertEqual(client.delete(f"/api/v1/config/participants/{identifier}/").status_code, 204)

    def test_valid_batch_is_visible_only_to_authorized_reader(self):
        response = self.send([self.packet()])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["inserted"], 1)
        reader = APIClient()
        reader.force_authenticate(self.reader)
        sessions = reader.get("/api/v1/sessions/")
        self.assertEqual(len(sessions.data["results"]), 1)
        history_url = f"/api/v1/sessions/{self.session.pk}/measurements/?source=simulated"
        history = reader.get(history_url)
        self.assertEqual(history.status_code, 200, history.data)
        self.assertEqual(history.data["count"], 1)
        self.assertEqual(history.data["results"][0]["value"], "78.000000000000")
        self.assertEqual(history.data["results"][0]["source"], "simulated")
        self.assertEqual(reader.get(history_url.split("?")[0]).status_code, 400)
        stranger = APIClient()
        stranger.force_authenticate(self.stranger)
        self.assertEqual(stranger.get(history_url).status_code, 404)
        self.assertEqual(stranger.get(f"/api/v1/sessions/{self.session.pk}/latest/?source=simulated").status_code, 404)
        self.assertEqual(self.device_client.get(history_url).status_code, 403)

    def test_missing_replay_conflict_and_atomicity(self):
        packet = self.packet(readings=[
            {"sensor_id": self.sensor.identifier, "metric": "heart_rate", "value": None, "unit": "bpm", "quality": "missing"}
        ])
        first = self.send([packet])
        self.assertEqual(first.status_code, 201, first.data)
        self.assertIsNone(Measurement.objects.get().value)
        replay = self.send([packet])
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(replay.data["duplicates"], 1)
        self.assertEqual(Measurement.objects.count(), 1)
        changed = dict(packet, readings=[dict(packet["readings"][0], value="0", quality="valid")])
        self.assertEqual(self.send([changed]).status_code, 409)
        valid = self.packet()
        invalid = self.packet(readings=[
            {"sensor_id": self.sensor.identifier, "metric": "heart_rate", "value": "80", "unit": "uSv", "quality": "valid"}
        ])
        self.assertEqual(self.send([valid, invalid]).status_code, 400)
        self.assertFalse(TelemetryPacket.objects.filter(packet_id=valid["packet_id"]).exists())

    def test_device_identity_and_revocation(self):
        packet = self.packet()
        self.assertEqual(self.send([packet], APIClient()).status_code, 401)
        invalid_client = APIClient()
        invalid_client.credentials(HTTP_AUTHORIZATION=f"Device {self.credential.pk}:wrong")
        self.assertEqual(self.send([packet], invalid_client).status_code, 401)
        self.assertEqual(self.send([dict(packet, device_id=self.other_device.identifier)]).status_code, 403)
        self.assertEqual(self.send([dict(packet, session_id=self.other_session.identifier)]).status_code, 403)
        self.credential.is_active = False
        self.credential.save(update_fields=["is_active"])
        self.assertEqual(self.send([packet]).status_code, 401)

    def test_invalid_contract_and_late_packet(self):
        self.assertEqual(self.send([self.packet()], version=2).status_code, 400)
        self.assertEqual(self.send([self.packet(value="NaN")]).status_code, 400)
        self.assertEqual(self.send([self.packet(value="Infinity")]).status_code, 400)
        self.assertEqual(self.send([dict(self.packet(), unexpected="field")]).status_code, 400)
        self.assertEqual(self.send([self.packet(observed_at=self.now + timedelta(hours=1))]).status_code, 400)
        current = self.packet(value="80", observed_at=self.now)
        late = self.packet(value="70", observed_at=self.now - timedelta(hours=1))
        self.assertEqual(self.send([current, late]).status_code, 201)
        reader = APIClient()
        reader.force_authenticate(self.reader)
        latest = reader.get(f"/api/v1/sessions/{self.session.pk}/latest/?source=simulated")
        self.assertEqual(latest.data["results"][0]["value"], "80.000000000000")

    def test_counter_epoch_is_preserved(self):
        packet = self.packet(readings=[
            {"sensor_id": self.dose_sensor.identifier, "metric": "absorbed_dose_cumulative", "value": "0.000000000001", "unit": "uGy", "quality": "valid", "counter_epoch": str(self.epoch.identifier)}
        ])
        self.assertEqual(self.send([packet]).status_code, 201)
        saved = Measurement.objects.get()
        self.assertEqual(saved.counter_epoch, self.epoch)
        self.assertEqual(str(saved.value), "1E-12")
        invalid = self.packet(readings=[dict(packet["readings"][0], counter_epoch=str(uuid.uuid4()))])
        self.assertEqual(self.send([invalid]).status_code, 400)

    @override_settings(TELEMETRY_MAX_BODY_BYTES=16)
    def test_body_size_is_limited(self):
        self.assertEqual(self.send([self.packet()]).status_code, 413)
