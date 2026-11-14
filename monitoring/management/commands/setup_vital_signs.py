"""Register synthetic watch channels on an existing monitoring session."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from monitoring.models import (
    Device,
    MonitoringSession,
    Sensor,
    SensorCapability,
    SessionDevice,
)
from monitoring.vital_signs import METRICS


class Command(BaseCommand):
    help = "Register studywatch-sim-001 and its five simulated channels in an existing session."

    def add_arguments(self, parser):
        parser.add_argument("session_identifier")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            session = MonitoringSession.objects.get(identifier=options["session_identifier"])
        except MonitoringSession.DoesNotExist as error:
            raise CommandError("Create the monitoring session first.") from error
        device, _ = Device.objects.get_or_create(identifier="studywatch-sim-001", defaults={"kind": "harness", "source": "simulated"})
        if device.source != "simulated":
            raise CommandError("Existing device is not simulated.")
        assignment, created = SessionDevice.objects.get_or_create(
            device=device, session=session, assigned_at=session.started_at,
            defaults={"released_at": session.ended_at},
        )
        assignment.full_clean()
        for metric, unit in METRICS.values():
            sensor, _ = Sensor.objects.get_or_create(
                identifier=f"{device.identifier}-{metric}",
                defaults={"device": device, "channel": metric, "profile_version": "vital-signs-demo.v1"},
            )
            if sensor.device_id != device.pk:
                raise CommandError("Existing channel belongs to another device.")
            capability, _ = SensorCapability.objects.get_or_create(sensor=sensor, metric=metric, unit=unit, defaults={"enabled": True})
            capability.full_clean()
        self.stdout.write("Configured studywatch-sim-001. Issue its credential with provision_device_token.")
