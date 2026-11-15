import io
import json
import random
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from monitoring.dosimeter_profile import DEVICE_ID
from monitoring.models import Device, Measurement
from monitoring.reports import build_report
from scripts.dosimeter import make_sample
from scripts.vital_signs import make_event

from .fixtures import TelemetryFixtures


class CombinedReportTests(TelemetryFixtures, TestCase):
    def setUp(self):
        super().setUp()
        out = io.StringIO()
        call_command("setup_dosimeter", self.session.identifier, reset_at=(self.now - timedelta(hours=1)).isoformat(), stdout=out)
        self.config = json.loads(out.getvalue())
        call_command("setup_vital_signs", self.session.identifier, stdout=io.StringIO())
        self.client = APIClient()
        self.client.force_authenticate(self.reader)
        self.url = f"/api/v1/sessions/{self.session.pk}/report/"
        self.params = {
            "source": "simulated", "observed_from": (self.now - timedelta(days=1)).isoformat(),
            "observed_to": (self.now + timedelta(seconds=1)).isoformat(),
        }

    def use_device(self, identifier):
        self.credential.device = Device.objects.get(identifier=identifier)
        self.credential.save()

    def send_vitals(self):
        self.use_device("studywatch-sim-001")
        event = make_event(0, 6, "baseline", random.Random(42), self.now - timedelta(seconds=10), uuid.uuid4().hex)
        response = self.device_client.post("/api/v1/telemetry/vital-signs/", event, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def send_dose(self, at=None):
        self.use_device(DEVICE_ID)
        packet, _ = make_sample(self.config, at or self.now)
        response = self.device_client.post("/api/v1/telemetry/batches/", {"schema_version": 1, "packets": [packet]}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return packet

    def test_both_ingestion_streams_in_json_and_text(self):
        self.send_vitals()
        self.send_dose()
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 200, response.data)
        report = response.data
        self.assertEqual(report["schema_version"], "combined-telemetry-report.v2")
        self.assertEqual(report["measurement_count"], 14)
        self.assertEqual(report["missing_domains"], [])
        self.assertEqual(report["domains"]["vital_signs"]["measurement_count"], 4)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn('.json"', response["Content-Disposition"])
        temperature = report["domains"]["body_temperature"]
        self.assertEqual(temperature["measurement_count"], 1)
        self.assertEqual(temperature["series"][0]["metric"], "skin_temperature")
        self.assertEqual(temperature["series"][0]["category"], "body_temperature")
        dose = report["domains"]["dosimeter"]
        self.assertEqual(dose["measurement_count"], 9)
        self.assertTrue(all(s["device_id"] == DEVICE_ID for s in dose["series"]))
        self.assertIn("internal_temperature", {s["metric"] for s in dose["series"]})
        ids = []
        for category, domain in report["domains"].items():
            for series in domain["series"]:
                row = series["readings"][0]
                self.assertEqual(row["category"], category)
                self.assertEqual(series["latest"]["category"], category)
                ids.extend(reading["id"] for reading in series["readings"])
                self.assertIn("received_at", row)
                self.assertIn("observed_at", row)
                self.assertEqual(row["source"], "simulated")
                self.assertTrue(row["value"] is None or isinstance(row["value"], str))
        self.assertEqual(len(set(ids)), 14)
        text = self.client.get(self.url, {**self.params, "output": "text"})
        self.assertEqual(text.status_code, 200)
        self.assertIn("text/plain", text["Content-Type"])
        self.assertIn(b"vital_signs: available (4 readings)", text.content)
        self.assertIn(b"dosimeter: available (9 readings)", text.content)
        self.assertEqual(text["Cache-Control"], "no-store")
        self.assertNotIn(self.participant.pseudonym, text.content.decode())
        self.assertEqual(Measurement.objects.count(), 14)

    def test_no_data_and_source_isolation(self):
        self.send_vitals()
        report = self.client.get(self.url, self.params).data
        self.assertEqual(report["missing_domains"], ["dosimeter"])
        report = self.client.get(self.url, {**self.params, "source": "hardware"}).data
        self.assertEqual(report["measurement_count"], 0)
        self.assertEqual(report["missing_domains"], ["vital_signs", "body_temperature", "dosimeter"])

    def test_permission_and_internal_service_isolation(self):
        self.send_dose()
        self.client.force_authenticate(self.stranger)
        self.assertEqual(self.client.get(self.url, self.params).status_code, 404)
        self.assertEqual(APIClient().get(self.url, self.params).status_code, 403)
        self.assertEqual(self.device_client.get(self.url, self.params).status_code, 403)
        with self.assertRaises(NotFound):
            build_report(user=self.stranger, session_id=self.session.pk, source="simulated",
                         observed_from=self.now - timedelta(days=1), observed_to=self.now)
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get(f"/api/v1/sessions/{self.other_session.pk}/report/", self.params).status_code, 404)

    def test_boundaries_validation_and_no_silent_truncation(self):
        self.send_dose()
        report = self.client.get(self.url, {**self.params, "observed_to": self.now.isoformat()}).data
        self.assertEqual(report["measurement_count"], 0)
        report = self.client.get(self.url, {**self.params, "observed_from": self.now.isoformat()}).data
        self.assertEqual(report["measurement_count"], 9)
        for changed in ({"source": "all"}, {"observed_from": "bad"}, {"observed_from": "2026-01-01T00:00:00"},
                        {"observed_from": "2026-02-30T00:00:00Z"}, {"observed_to": self.params["observed_from"]},
                        {"observed_from": (self.now - timedelta(days=32)).isoformat()}, {"metric": "heart_rate"}, {"output": "pdf"}):
            self.assertEqual(self.client.get(self.url, {**self.params, **changed}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"source": "simulated"}).status_code, 400)
        with patch("monitoring.reports.MAX_REPORT_READINGS", 8):
            response = self.client.get(self.url, self.params)
            self.assertEqual(response.status_code, 400)
            self.assertIn("smaller observation window", str(response.data))

    def test_counter_epochs_and_quality_remain_distinct(self):
        self.send_dose(self.now - timedelta(hours=2))
        self.send_dose(self.now)
        report = self.client.get(self.url, self.params).data
        series = report["domains"]["dosimeter"]["series"]
        counters = [s for s in series if s["metric"] == "absorbed_dose_cumulative"]
        self.assertEqual(len(counters), 2)
        self.assertNotEqual(counters[0]["counter_epoch"], counters[1]["counter_epoch"])
        intervals = next(s for s in series if s["metric"] == "measurement_interval")
        self.assertEqual(intervals["quality_counts"]["missing"], 2)
        self.assertIsNone(intervals["latest"]["value"])
        self.assertLess(intervals["readings"][0]["observed_at"], intervals["readings"][1]["observed_at"])

    def test_missing_temperature_keeps_tag_and_null(self):
        self.use_device("studywatch-sim-001")
        event = make_event(2, 6, "signal-loss", random.Random(42), self.now - timedelta(seconds=10), uuid.uuid4().hex)
        response = self.device_client.post("/api/v1/telemetry/vital-signs/", event, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        report = self.client.get(self.url, self.params).data
        row = report["domains"]["body_temperature"]["series"][0]["readings"][0]
        self.assertEqual(row["category"], "body_temperature")
        self.assertEqual(row["quality"], "missing")
        self.assertIsNone(row["value"])

    def test_schema_describes_report_not_paginated(self):
        schema = APIClient().get("/api/v1/schema/?format=json").data
        response = schema["paths"]["/api/v1/sessions/{id}/report/"]["get"]["responses"]["200"]["content"]
        self.assertIn("text/plain", response)
        self.assertEqual(response["application/json"]["schema"]["$ref"], "#/components/schemas/CombinedReport")
