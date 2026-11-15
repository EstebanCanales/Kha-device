import base64
from datetime import timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from .fixtures import TelemetryFixtures


class SessionEndpointTests(TelemetryFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.reader)
        self.detail = f"/api/v1/sessions/{self.session.pk}/"

    def test_reader_can_list_retrieve_but_cannot_mutate(self):
        response = self.client.get("/api/v1/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [str(self.session.pk)])
        self.assertEqual(self.client.get(self.detail).status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/sessions/{self.other_session.pk}/").status_code, 404)
        for method, url in (("post", "/api/v1/sessions/"), ("put", self.detail), ("patch", self.detail), ("delete", self.detail)):
            self.assertEqual(getattr(self.client, method)(url, {}, format="json").status_code, 403)

    def test_staff_session_crud_and_protected_delete(self):
        self.client.force_authenticate(self.staff)
        data = {"identifier": "session-crud", "participant": str(self.participant.pk), "started_at": self.now.isoformat(), "authorized_users": [self.reader.pk]}
        response = self.client.post("/api/v1/sessions/", data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        detail = f"/api/v1/sessions/{response.data['id']}/"
        updated = self.client.put(detail, {**data, "gravity_context": "earth"}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.client.patch(detail, {"gravity_context": "unknown"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertEqual(self.client.delete(self.detail).status_code, 409)

    def test_basic_authentication_and_invalid_password(self):
        client = APIClient()
        encoded = base64.b64encode(b"reader:reader-password").decode()
        client.credentials(HTTP_AUTHORIZATION=f"Basic {encoded}")
        self.assertEqual(client.get(self.detail).status_code, 200)
        encoded = base64.b64encode(b"reader:wrong").decode()
        client.credentials(HTTP_AUTHORIZATION=f"Basic {encoded}")
        self.assertEqual(client.get(self.detail).status_code, 403)

    def test_history_pagination_filtering_and_latest(self):
        late = self.packet(value="72", observed_at=self.now - timedelta(seconds=20))
        newest = self.packet(value="80")
        middle = self.packet(value="75", observed_at=self.now - timedelta(seconds=10))
        self.assertEqual(self.send([newest, late, middle]).status_code, 201)
        url = self.detail + "measurements/"
        params = {"source": "simulated", "page_size": 2}
        response = self.client.get(url, params)
        self.assertEqual(response.data["count"], 3)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual([row["value"] for row in response.data["results"]], ["72.000000000000", "75.000000000000"])
        page2 = self.client.get(url, {**params, "page": 2})
        self.assertEqual(page2.data["results"][0]["value"], "80.000000000000")
        filtered = self.client.get(url, {"source": "simulated", "metric": "heart_rate", "sensor": self.sensor.identifier, "observed_from": self.now.isoformat(), "observed_to": self.now.isoformat()})
        self.assertEqual(filtered.data["count"], 1)
        latest = self.client.get(self.detail + "latest/", {"source": "simulated"})
        self.assertEqual(latest.data["count"], 1)
        self.assertEqual(latest.data["results"][0]["packet_id"], newest["packet_id"])
        self.assertEqual(self.client.get(url, {"source": "hardware"}).data["count"], 0)
        self.assertEqual(self.client.get(url, {"source": "simulated", "sensor": "unknown"}).data["count"], 0)

    def test_history_invalid_filters_return_400(self):
        for action in ("measurements/", "latest/"):
            for query in ({}, {"source": "invalid"}, {"source": "simulated", "metric": "unknown"},
                          {"source": "simulated", "observed_from": "bad"},
                          {"source": "simulated", "observed_from": "2026-02-30T00:00:00Z"},
                          {"source": "simulated", "observed_to": "2026-01-01T00:00:00"},
                          {"source": "simulated", "observed_from": self.now.isoformat(), "observed_to": (self.now - timedelta(days=1)).isoformat()},
                          {"source": "simulated", "observed_from": self.now.isoformat(), "observed_to": (self.now + timedelta(days=32)).isoformat()}):
                with self.subTest(action=action, query=query):
                    self.assertEqual(self.client.get(self.detail + action, query).status_code, 400)

    def test_observation_routes_are_read_only(self):
        self.client.force_authenticate(self.staff)
        for action in ("measurements/", "latest/", "report/"):
            for method in ("post", "put", "patch", "delete"):
                self.assertEqual(getattr(self.client, method)(self.detail + action, {}, format="json").status_code, 405)
