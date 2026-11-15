"""Exercise every configuration collection/detail route and CRUD verb."""

from django.test import TestCase
from rest_framework.test import APIClient

from monitoring.models import Sensor

from .fixtures import TelemetryFixtures


class ConfigurationEndpointTests(TelemetryFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.extra_sensor = Sensor.objects.create(identifier="extra-counter", device=self.device, channel="extra-counter")

    def cases(self):
        return [
            ("participants", self.participant.pk, {"pseudonym": "synthetic-crud"}, {"pseudonym": "synthetic-renamed"}),
            ("devices", self.device.pk, {"identifier": "new-device", "kind": "dosimeter", "source": "simulated"}, {"firmware_version": "test-v2"}),
            ("sensors", self.sensor.pk, {"identifier": "new-sensor", "device": str(self.device.pk), "channel": "new-channel"}, {"body_site": "synthetic-site"}),
            ("capabilities", self.sensor.capabilities.get().pk, {"sensor": str(self.sensor.pk), "metric": "pulse_rate", "unit": "bpm", "enabled": True}, {"enabled": False}),
            ("assignments", self.assignment.pk, {"session": str(self.session.pk), "device": str(self.other_device.pk), "assigned_at": self.session.started_at.isoformat()}, {"released_at": self.now.isoformat()}),
            ("counter-epochs", self.epoch.pk, {"assignment": str(self.assignment.pk), "sensor": str(self.extra_sensor.pk), "started_at": self.session.started_at.isoformat()}, {"reference": "synthetic-reference-v2"}),
        ]

    def test_all_configuration_routes_support_staff_crud(self):
        for resource, existing_id, payload, changes in self.cases():
            with self.subTest(resource=resource):
                url = f"/api/v1/config/{resource}/"
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.get(f"{url}{existing_id}/").status_code, 200)
                created = self.client.post(url, payload, format="json")
                self.assertEqual(created.status_code, 201, created.data)
                detail = f"{url}{created.data['id']}/"
                for method in (self.client.put, self.client.patch):
                    data = {**payload, **changes} if method == self.client.put else changes
                    updated = method(detail, data, format="json")
                    self.assertEqual(updated.status_code, 200, updated.data)
                    for key, value in changes.items():
                        if key != "released_at":
                            self.assertEqual(updated.data[key], value)
                self.assertEqual(self.client.delete(detail).status_code, 204)
                self.assertEqual(self.client.get(detail).status_code, 404)

    def test_all_configuration_methods_require_staff(self):
        for user in (None, self.reader):
            client = APIClient()
            if user:
                client.force_authenticate(user)
            for resource, identifier, payload, changes in self.cases():
                url = f"/api/v1/config/{resource}/"
                detail = f"{url}{identifier}/"
                for method, target, data in (("get", url, None), ("get", detail, None), ("post", url, payload),
                                             ("put", detail, payload), ("patch", detail, changes), ("delete", detail, None)):
                    with self.subTest(user=user, resource=resource, method=method):
                        response = getattr(client, method)(target, data, format="json")
                        self.assertEqual(response.status_code, 403)

    def test_referenced_configuration_cannot_be_deleted(self):
        self.assertEqual(self.send([self.packet()]).status_code, 201)
        for resource, identifier, _, _ in self.cases():
            with self.subTest(resource=resource):
                # The fixture epoch has no readings yet; make it referenced too.
                if resource == "counter-epochs":
                    packet = self.packet(readings=[{"sensor_id": self.dose_sensor.identifier, "metric": "absorbed_dose_cumulative", "value": "1", "unit": "uGy", "quality": "valid", "counter_epoch": str(self.epoch.identifier)}])
                    self.assertEqual(self.send([packet]).status_code, 201)
                self.assertEqual(self.client.delete(f"/api/v1/config/{resource}/{identifier}/").status_code, 409)

    def test_incompatible_unit_and_overlapping_assignment_rejected(self):
        response = self.client.post("/api/v1/config/capabilities/", {"sensor": str(self.sensor.pk), "metric": "heart_rate", "unit": "uGy", "enabled": True}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/v1/config/assignments/", {"session": str(self.other_session.pk), "device": str(self.device.pk), "assigned_at": self.now.isoformat()}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_session_authentication_requires_csrf_for_mutations(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.get("/api/v1/config/participants/").status_code, 200)
        self.assertEqual(client.post("/api/v1/config/participants/", {"pseudonym": "csrf-test"}, format="json").status_code, 403)

    def test_counter_constraints_remain_enforced_after_partial_update_fix(self):
        url = "/api/v1/config/counter-epochs/"
        duplicate = self.client.post(url, {
            "assignment": str(self.assignment.pk), "sensor": str(self.dose_sensor.pk),
            "started_at": self.now.isoformat(),
        }, format="json")
        self.assertEqual(duplicate.status_code, 400)
        detail = f"{url}{self.epoch.pk}/"
        invalid_end = self.client.patch(detail, {"ended_at": self.session.started_at.isoformat()}, format="json")
        self.assertEqual(invalid_end.status_code, 400)
        self.epoch.refresh_from_db()
        self.assertIsNone(self.epoch.ended_at)
