"""Synthetic NASA-shaped fixtures; never require external credentials or network."""

import io
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from monitoring.models import Measurement, TelemetryPacket
from monitoring.nasa_radiation import (
    MAX_BYTES,
    RadiationUnavailable,
    fetch_radiation_events,
)

from .fixtures import TelemetryFixtures

EVENT = {
    "rbeID": "2024-05-15T13:55:00-RBE-SYNTHETIC",
    "eventTime": "2024-05-15T13:55Z",
    "instruments": [{"displayName": "Synthetic instrument"}],
    "linkedEvents": None,
}


class RadiationClientTests(SimpleTestCase):
    def fetch(self):
        return fetch_radiation_events("2024-05-01", "2024-05-15", api_key="synthetic-secret")

    @patch("monitoring.nasa_radiation.urlopen")
    def test_preserves_events_and_provenance_without_key(self, opener):
        opener.return_value = io.BytesIO(json.dumps([EVENT]).encode())
        result = self.fetch()
        self.assertEqual(result["events"], [EVENT])
        self.assertFalse(result["personal_dose_available"])
        self.assertNotIn("synthetic-secret", json.dumps(result))
        request = opener.call_args.args[0]
        self.assertIn("api_key=synthetic-secret", request.full_url)
        self.assertEqual(opener.call_args.kwargs["timeout"], 15)

    @patch("monitoring.nasa_radiation.urlopen")
    def test_empty_results_and_malformed_responses(self, opener):
        for body in (b"[]", b"null"):
            opener.return_value = io.BytesIO(body)
            self.assertEqual(self.fetch()["event_count"], 0)
        for body in (b"", b"not json", b"{}", b"[{}]", b"[1]", b"x" * (MAX_BYTES + 1),
                     json.dumps([dict(EVENT, eventTime="2024-05-15T13:55")]).encode(),
                     json.dumps([dict(EVENT, eventTime="2024-06-01T00:00Z")]).encode()):
            opener.return_value = io.BytesIO(body)
            with self.assertRaises(RadiationUnavailable):
                self.fetch()

    @patch("monitoring.nasa_radiation.urlopen")
    def test_configuration_and_invalid_windows_do_not_call_nasa(self, opener):
        with self.assertRaises(RadiationUnavailable):
            fetch_radiation_events("2024-05-01", "2024-05-15", api_key="")
        for start, end in (("bad", "2024-05-15"), ("2024-05-16", "2024-05-15"),
                           ("2024-05-01", "2024-06-01"), ("20240501", "2024-05-15")):
            with self.assertRaises(ValueError):
                fetch_radiation_events(start, end, api_key="synthetic")
        opener.assert_not_called()

    @patch("monitoring.nasa_radiation.urlopen")
    def test_network_errors_hide_credentials(self, opener):
        errors = [URLError("synthetic-secret"), TimeoutError("synthetic-secret")]
        errors.extend(HTTPError("https://example.test/?api_key=synthetic-secret", code,
                                "synthetic-secret", {}, None) for code in (403, 429, 500))
        for error in errors:
            opener.side_effect = error
            with self.assertRaises(RadiationUnavailable) as caught:
                self.fetch()
            self.assertNotIn("synthetic-secret", str(caught.exception))


@override_settings(RADATION_API_KEY="synthetic-key")
class RadiationEndpointTests(TelemetryFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/v1/sessions/{self.session.pk}/radiation-context/"
        self.query = {"start_date": "2024-05-01", "end_date": "2024-05-15"}
        self.client = APIClient()

    @patch("monitoring.views.fetch_radiation_events")
    def test_authorization_before_fetch_or_cache(self, fetch):
        cache.set("nasa-rbe:2024-05-01:2024-05-15", {"events": [EVENT]})
        self.assertIn(self.client.get(self.url, self.query).status_code, (401, 403))
        self.assertIn(self.device_client.get(self.url, self.query).status_code, (401, 403))
        self.client.force_authenticate(self.stranger)
        self.assertEqual(self.client.get(self.url, self.query).status_code, 404)
        fetch.assert_not_called()

    @patch("monitoring.views.fetch_radiation_events")
    def test_cache_and_no_telemetry_writes(self, fetch):
        fetch.return_value = {"events": [EVENT], "source": "nasa_donki"}
        self.client.force_authenticate(self.reader)
        for _ in range(2):
            response = self.client.get(self.url, self.query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["source"], "nasa_donki")
        fetch.assert_called_once_with(**self.query, api_key="synthetic-key")
        self.assertEqual(Measurement.objects.count(), 0)
        self.assertEqual(TelemetryPacket.objects.count(), 0)

    @patch("monitoring.views.fetch_radiation_events")
    def test_validation_configuration_and_upstream_failure(self, fetch):
        self.client.force_authenticate(self.reader)
        for query in ({}, dict(self.query, start_date="invalid"), dict(self.query, unexpected="x")):
            self.assertEqual(self.client.get(self.url, query).status_code, 400)
        with override_settings(RADATION_API_KEY=""):
            self.assertEqual(self.client.get(self.url, self.query).status_code, 503)
        fetch.assert_not_called()
        fetch.side_effect = RadiationUnavailable("NASA DONKI could not be reached.")
        self.assertEqual(self.client.get(self.url, self.query).status_code, 503)
        self.assertIsNone(cache.get("nasa-rbe:2024-05-01:2024-05-15"))

    @patch("monitoring.views.fetch_radiation_events", return_value={"events": []})
    def test_request_throttle(self, fetch):
        self.client.force_authenticate(self.reader)
        for _ in range(30):
            self.assertEqual(self.client.get(self.url, self.query).status_code, 200)
        self.assertEqual(self.client.get(self.url, self.query).status_code, 429)
