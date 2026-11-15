from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from monitoring.models import Measurement, TelemetryPacket

from .fixtures import TelemetryFixtures


class PublicEndpointTests(TestCase):
    def test_health_and_readiness_are_public(self):
        for route in ("/healthz/", "/readyz/"):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_database_failure_returns_503_without_details(self):
        with patch("monitoring.views.connection.cursor", side_effect=OperationalError("private database details")):
            response = self.client.get("/readyz/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_schema_covers_every_application_api_route(self):
        response = APIClient().get("/api/v1/schema/?format=json")
        self.assertEqual(response.status_code, 200)
        paths = response.data["paths"]
        expected = {"/api/v1/schema/", "/api/v1/telemetry/batches/", "/api/v1/telemetry/vital-signs/", "/api/v1/sessions/", "/api/v1/sessions/{id}/"}
        expected.update(f"/api/v1/sessions/{{id}}/{action}/" for action in ("measurements", "latest", "report"))
        for resource in ("participants", "devices", "sensors", "capabilities", "assignments", "counter-epochs"):
            expected.update({f"/api/v1/config/{resource}/", f"/api/v1/config/{resource}/{{id}}/"})
        self.assertEqual(set(paths), expected)
        for route in ("/api/v1/telemetry/batches/", "/api/v1/telemetry/vital-signs/"):
            self.assertEqual(paths[route]["post"]["security"], [{"DeviceCredential": []}])


class AdminEndpointTests(TelemetryFixtures, TestCase):
    def test_admin_requires_staff_and_telemetry_is_immutable(self):
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        # Use superuser to ensure denials below are due to immutability, not missing grants.
        admin = get_user_model().objects.create_superuser("synthetic-admin", password="test-admin-password")
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.send([self.packet()]).status_code, 201)
        for name, obj in (("measurement", Measurement.objects.get()), ("telemetrypacket", TelemetryPacket.objects.get())):
            detail = reverse(f"admin:monitoring_{name}_change", args=[obj.pk])
            self.assertEqual(self.client.get(detail).status_code, 200)
            self.assertEqual(self.client.post(detail, {"value": "999"}).status_code, 403)
            self.assertEqual(self.client.post(reverse(f"admin:monitoring_{name}_delete", args=[obj.pk]), {"post": "yes"}).status_code, 403)
        self.assertEqual(str(Measurement.objects.get().value), "78.000000000000")
