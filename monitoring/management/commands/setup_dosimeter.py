"""Configure a separate, explicitly synthetic dosimeter without altering existing profiles."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from monitoring.dosimeter_profile import CHANNELS, DEVICE_ID, PROFILE_VERSION
from monitoring.models import (
    CounterEpoch,
    Device,
    MonitoringSession,
    Sensor,
    SensorCapability,
    SessionDevice,
)


class Command(BaseCommand):
    help = "Register a simulated dosimeter; print its non-secret simulator configuration as JSON."

    def add_arguments(self, parser):
        parser.add_argument("session_identifier")
        parser.add_argument("--reset-at", help="Optional timezone-aware synthetic counter reset time")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            session = MonitoringSession.objects.get(identifier=options["session_identifier"])
        except MonitoringSession.DoesNotExist as error:
            raise CommandError("Create the session first.") from error
        reset_at = parse_datetime(options["reset_at"]) if options["reset_at"] else None
        if options["reset_at"] and (reset_at is None or reset_at.utcoffset() is None or reset_at <= session.started_at or (session.ended_at and reset_at >= session.ended_at)):
            raise CommandError("Reset time must be timezone-aware and inside the session.")
        device, _ = Device.objects.get_or_create(identifier=DEVICE_ID, defaults={"kind": "dosimeter", "source": "simulated"})
        if device.source != "simulated" or device.kind != "dosimeter" or not device.is_active:
            raise CommandError("Existing device has an incompatible profile.")
        assignment, _ = SessionDevice.objects.get_or_create(
            device=device, session=session, assigned_at=session.started_at,
            defaults={"released_at": session.ended_at},
        )
        assignment.full_clean()
        sensors = {}
        for metric, unit in CHANNELS.items():
            sensor, _ = Sensor.objects.get_or_create(identifier=f"{DEVICE_ID}-{metric}", defaults={
                "device": device, "channel": metric, "profile_version": PROFILE_VERSION,
            })
            if sensor.device_id != device.pk or sensor.profile_version != PROFILE_VERSION or not sensor.is_active:
                raise CommandError("Existing sensor has an incompatible profile.")
            capability, _ = SensorCapability.objects.get_or_create(sensor=sensor, metric=metric, unit=unit, defaults={"enabled": True})
            if not capability.enabled:
                raise CommandError("Existing capability is disabled.")
            capability.full_clean()
            sensors[metric] = sensor
        epochs = []
        periods = [(session.started_at, reset_at or session.ended_at)]
        if reset_at:
            periods.append((reset_at, session.ended_at))
        for start, end in periods:
            epoch, _ = CounterEpoch.objects.get_or_create(
                assignment=assignment, sensor=sensors["absorbed_dose_cumulative"], started_at=start,
                defaults={"ended_at": end, "reference": PROFILE_VERSION},
            )
            if epoch.ended_at != end:
                raise CommandError("Existing epochs differ. Do not rewrite counter history; use a new session/profile.")
            epoch.full_clean()
            epochs.append({"id": str(epoch.identifier), "started_at": start.isoformat(), "ended_at": end.isoformat() if end else None})
        self.stdout.write(json.dumps({
            "profile_version": PROFILE_VERSION, "device_id": DEVICE_ID,
            "session_id": session.identifier, "session_uuid": str(session.pk),
            "mission_started_at": session.started_at.isoformat(), "epochs": epochs,
        }, indent=2))
