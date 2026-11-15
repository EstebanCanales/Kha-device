import copy
import io
import json
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from monitoring.dosimeter_profile import DEVICE_ID
from monitoring.models import Device, Measurement
from scripts.dosimeter import Journal, make_sample

from .fixtures import TelemetryFixtures


class DosimeterTests(TelemetryFixtures, TestCase):
    def setUp(self):
        super().setUp()
        output = io.StringIO()
        self.reset = self.now - timedelta(hours=1)
        call_command("setup_dosimeter", self.session.identifier, reset_at=self.reset.isoformat(), stdout=output)
        self.config = json.loads(output.getvalue())
        self.credential.device = Device.objects.get(identifier=DEVICE_ID)
        self.credential.save()

    def send(self, packet):
        return self.device_client.post("/api/v1/telemetry/batches/", {"schema_version": 1, "packets": [packet]}, format="json")

    def test_full_history_duplicate_conflict_and_authorization(self):
        packet, _ = make_sample(self.config, self.now)
        self.assertEqual(self.send(packet).status_code, 201)
        self.assertEqual(Measurement.objects.count(), 9)
        self.assertEqual(self.send(packet).status_code, 200)
        changed = copy.deepcopy(packet)
        changed["readings"][0]["value"] = "99"
        self.assertEqual(self.send(changed).status_code, 409)
        reader = APIClient()
        reader.force_authenticate(self.reader)
        url = f"/api/v1/sessions/{self.session.pk}/measurements/?source=simulated"
        response = reader.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 9)
        reader.force_authenticate(self.stranger)
        self.assertEqual(reader.get(url).status_code, 404)
        wrong = dict(packet, device_id="another-device")
        self.assertEqual(self.send(wrong).status_code, 403)
        self.credential.is_active = False
        self.credential.save()
        self.assertEqual(self.send(packet).status_code, 401)

    def test_reset_missing_and_time_intervals(self):
        old, state = make_sample(self.config, self.reset - timedelta(seconds=2))
        self.assertEqual(self.send(old).status_code, 201)
        missing, state = make_sample(self.config, self.reset, state, scenario="signal-loss")
        self.assertEqual(self.send(missing).status_code, 201)
        self.assertNotEqual(old["readings"][1]["counter_epoch"], missing["readings"][1]["counter_epoch"])
        self.assertIsNone(missing["readings"][0]["value"])
        self.assertIsNone(missing["readings"][1]["value"])
        self.assertEqual(missing["readings"][3]["value"], "2")
        self.assertEqual(missing["readings"][6]["value"], "2")
        recovered, _ = make_sample(self.config, self.reset + timedelta(seconds=3), state)
        self.assertIsNone(recovered["readings"][-1]["value"])
        self.assertEqual(self.send(recovered).status_code, 201)
        invalid = copy.deepcopy(recovered)
        invalid["packet_id"] = old["packet_id"]
        invalid["readings"][1]["counter_epoch"] = old["readings"][1]["counter_epoch"]
        # Fresh identity ensures validation reaches the epoch boundary check.
        import uuid
        invalid["packet_id"] = str(uuid.uuid4())
        self.assertEqual(self.send(invalid).status_code, 400)

    def test_units_and_status_validation(self):
        packet, _ = make_sample(self.config, self.now)
        from monitoring.models import SensorCapability
        SensorCapability.objects.create(sensor=Device.objects.get(identifier=DEVICE_ID).sensors.get(channel="absorbed_dose_rate"), metric="absorbed_dose_rate", unit="uGy/min", enabled=True)
        packet["readings"][0]["unit"] = "uGy/min"
        self.assertEqual(self.send(packet).status_code, 201)
        for value in ("3", "1.5", "NaN"):
            bad, _ = make_sample(self.config, self.now)
            bad["readings"][6]["value"] = value
            self.assertEqual(self.send(bad).status_code, 400)
        self.assertEqual(Measurement.objects.count(), 9)

    def test_spike_and_durable_replay_after_failure(self):
        state = None
        packets = []
        for index in range(4):
            packet, state = make_sample(self.config, self.now - timedelta(seconds=4-index), state, scenario="spike")
            packets.append((packet, state))
        self.assertGreater(Decimal(packets[2][0]["readings"][0]["value"]), Decimal(packets[1][0]["readings"][0]["value"]))
        self.assertEqual(packets[2][0]["readings"][-1]["value"], "1")
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/journal.sqlite3"
            journal = Journal(path, self.config)
            for packet, state in packets:
                journal.append(packet, state)
            def failed_sender(*args):
                raise ValueError("offline")
            with self.assertRaises(ValueError):
                journal.replay("unused", "unused", sender=failed_sender)
            journal.close()
            journal = Journal(path, self.config)
            self.assertEqual(journal.last_state(), state)
            def api_sender(url, token, packet):
                self.assertIn(self.send(packet).status_code, (200, 201))
            journal.replay("unused", "unused", duplicate=True, sender=api_sender)
            self.assertEqual(Measurement.objects.count(), 36)
            self.assertEqual(journal.db.execute("SELECT COUNT(*) FROM samples WHERE sent=0").fetchone()[0], 0)
            self.assertEqual(journal.db.execute("SELECT COUNT(*) FROM samples").fetchone()[0], 4)
            journal.close()
