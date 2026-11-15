import uuid
from datetime import timedelta

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from monitoring.models import (
    Measurement,
    TelemetryPacket,
)

from .fixtures import TelemetryFixtures


class TelemetryAPITests(TelemetryFixtures, TestCase):
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

    def test_staff_can_create_connected_configuration_through_api(self):
        client = APIClient()
        client.force_authenticate(self.staff)
        session = client.post("/api/v1/sessions/", {
            "identifier": "session-api-created", "participant": str(self.participant.pk),
            "started_at": (self.now - timedelta(days=1)).isoformat(),
            "authorized_users": [self.reader.pk],
        }, format="json")
        self.assertEqual(session.status_code, 201, session.data)
        device = client.post("/api/v1/config/devices/", {
            "identifier": "dose-api-created", "kind": "dosimeter", "source": "simulated"
        }, format="json")
        self.assertEqual(device.status_code, 201, device.data)
        sensor = client.post("/api/v1/config/sensors/", {
            "identifier": "dose-channel-api", "device": str(device.data["id"]), "channel": "dose"
        }, format="json")
        self.assertEqual(sensor.status_code, 201, sensor.data)
        bad_capability = client.post("/api/v1/config/capabilities/", {
            "sensor": str(sensor.data["id"]), "metric": "absorbed_dose_cumulative", "unit": "uSv", "enabled": True
        }, format="json")
        self.assertEqual(bad_capability.status_code, 400)
        capability = client.post("/api/v1/config/capabilities/", {
            "sensor": str(sensor.data["id"]), "metric": "absorbed_dose_cumulative", "unit": "uGy", "enabled": True
        }, format="json")
        self.assertEqual(capability.status_code, 201, capability.data)
        assignment = client.post("/api/v1/config/assignments/", {
            "session": str(session.data["id"]), "device": str(device.data["id"]),
            "assigned_at": (self.now - timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(assignment.status_code, 201, assignment.data)
        epoch = client.post("/api/v1/config/counter-epochs/", {
            "assignment": str(assignment.data["id"]), "sensor": str(sensor.data["id"]),
            "started_at": (self.now - timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(epoch.status_code, 201, epoch.data)
        self.assertTrue(epoch.data["identifier"])
        reader = APIClient()
        reader.force_authenticate(self.reader)
        self.assertEqual(reader.get("/api/v1/sessions/").data["count"], 2)

    def test_openapi_schema_lists_ingestion_and_history(self):
        response = APIClient().get("/api/v1/schema/?format=json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/v1/telemetry/batches/", response.data["paths"])
        self.assertIn("DeviceCredential", response.data["components"]["securitySchemes"])

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
