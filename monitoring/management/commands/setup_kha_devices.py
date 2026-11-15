"""Register the two Kha-device 01 devices as explicitly simulated profiles.

Device 1 is the Crew Active Dosimeter (CAD); device 2 carries the MAX86178 and
MAX30205 sensors. Part numbers come from the project notes. Sampling, payloads,
and calibration are not verified, so every profile here is simulated.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from monitoring.models import (
    CounterEpoch,
    Device,
    Metric,
    MonitoringSession,
    Participant,
    Sensor,
    SensorCapability,
    SessionDevice,
)

CAD = "cad-sim-001"
VITALS = "kha-vitals-sim-001"

# (sensor identifier, device, channel, body site, profile version, calibration note, metrics)
SENSORS = (
    (
        "cad-dis-high-001", CAD, "dis_high", "", "cad-dis-high.v1",
        "DIS high-resolution chamber, saturation approx. 500-700 mGy (project notes, unverified)",
        ((Metric.ABSORBED_DOSE_CUMULATIVE, "mGy"),),
    ),
    (
        "cad-dis-low-001", CAD, "dis_low", "", "cad-dis-low.v1",
        "DIS low-resolution chamber, saturation approx. 5-7 Gy (project notes, unverified)",
        ((Metric.ABSORBED_DOSE_CUMULATIVE, "mGy"),),
    ),
    ("cad-exposure-001", CAD, "exposure", "", "cad-exposure.v1", "", ((Metric.EXPOSURE_DURATION, "s"),)),
    (
        "cad-tmp117-001", CAD, "internal_temperature", "", "tmp117.v1",
        "Internal electronics temperature for thermal compensation; not a body temperature",
        ((Metric.INTERNAL_TEMPERATURE, "degC"),),
    ),
    (
        "max86178-ppg-001", VITALS, "ppg", "", "max86178-ppg.v1", "",
        ((Metric.HEART_RATE, "bpm"), (Metric.PULSE_RATE, "bpm"), (Metric.SPO2, "%"), (Metric.RESPIRATORY_RATE, "breaths/min")),
    ),
    ("max30205-001", VITALS, "skin_temperature", "skin", "max30205.v1", "", ((Metric.SKIN_TEMPERATURE, "degC"),)),
)


class Command(BaseCommand):
    help = "Create a synthetic participant, session, and the CAD and vital-signs device profiles."

    def add_arguments(self, parser):
        parser.add_argument("--session", default="session-kha-001")
        parser.add_argument("--reader", help="Existing username allowed to read the session")

    @transaction.atomic
    def handle(self, *args, **options):
        reader = None
        if options["reader"]:
            reader = get_user_model().objects.filter(username=options["reader"], is_active=True).first()
            if reader is None:
                raise CommandError("Reader user does not exist or is inactive.")
        started = timezone.now().replace(microsecond=0) - timedelta(days=1)
        session = MonitoringSession.objects.filter(identifier=options["session"]).first()
        if session is None:
            participant, _ = Participant.objects.get_or_create(pseudonym="synthetic-kha-001")
            session = MonitoringSession.objects.create(
                identifier=options["session"], participant=participant, started_at=started,
                gravity_context="unknown",
            )
        if reader:
            session.authorized_users.add(reader)

        assignments = {}
        for identifier, kind in ((CAD, Device.Kind.DOSIMETER), (VITALS, Device.Kind.HARNESS)):
            device, _ = Device.objects.get_or_create(
                identifier=identifier, defaults={"kind": kind, "source": Device.Source.SIMULATED}
            )
            if device.kind != kind or device.source != Device.Source.SIMULATED:
                raise CommandError(f"{identifier} already exists with an incompatible profile.")
            assignment = SessionDevice.objects.filter(device=device, session=session, released_at__isnull=True).first()
            if assignment is None:
                if SessionDevice.objects.filter(device=device, released_at__isnull=True).exists():
                    raise CommandError(f"{identifier} is already assigned elsewhere.")
                assignment = SessionDevice.objects.create(session=session, device=device, assigned_at=session.started_at)
            assignments[identifier] = (device, assignment)

        for identifier, device_id, channel, site, profile, calibration, metrics in SENSORS:
            device, _ = assignments[device_id]
            sensor, _ = Sensor.objects.get_or_create(
                identifier=identifier,
                defaults={
                    "device": device, "channel": channel, "body_site": site,
                    "profile_version": profile, "calibration_reference": calibration,
                },
            )
            if sensor.device_id != device.pk:
                raise CommandError(f"{identifier} already belongs to another device.")
            for metric, unit in metrics:
                SensorCapability.objects.get_or_create(sensor=sensor, metric=metric, unit=unit, defaults={"enabled": True})

        # Each DIS chamber is its own cumulative counter, so each gets its own epoch.
        cad_assignment = assignments[CAD][1]
        self.stdout.write(f"session_uuid={session.pk}")
        self.stdout.write(f"session_identifier={session.identifier}")
        for key, sensor_identifier in (("epoch_high", "cad-dis-high-001"), ("epoch_low", "cad-dis-low-001")):
            sensor = Sensor.objects.get(identifier=sensor_identifier)
            epoch = CounterEpoch.objects.filter(assignment=cad_assignment, sensor=sensor, ended_at__isnull=True).first()
            if epoch is None:
                epoch = CounterEpoch.objects.create(
                    assignment=cad_assignment, sensor=sensor, started_at=session.started_at,
                    reference="synthetic-cad-start",
                )
            self.stdout.write(f"{key}={epoch.identifier}")
