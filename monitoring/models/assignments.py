"""Time-bounded device/session assignments and cumulative-counter epochs."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from .participants import MonitoringSession
from .sensors import Device, Sensor
from .shared import UUIDPrimaryKeyModel


class SessionDevice(UUIDPrimaryKeyModel):
    session = models.ForeignKey(MonitoringSession, on_delete=models.PROTECT, related_name="device_assignments")
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="session_assignments")
    assigned_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(released_at__isnull=True) | Q(released_at__gt=F("assigned_at")), name="assignment_end_after_start"),
            models.UniqueConstraint(fields=["session", "device", "assigned_at"], name="unique_assignment_start"),
            models.UniqueConstraint(fields=["device"], condition=Q(released_at__isnull=True), name="one_open_assignment_per_device"),
        ]
        indexes = [models.Index(fields=["device", "assigned_at"])]

    def clean(self):
        if not self.device_id or not self.session_id or not self.assigned_at:
            return
        if self.assigned_at < self.session.started_at or (
            self.session.ended_at and (not self.released_at or self.released_at > self.session.ended_at)
        ):
            raise ValidationError("Assignment must be within the monitoring session.")
        overlaps = SessionDevice.objects.filter(device_id=self.device_id).exclude(pk=self.pk)
        overlaps = overlaps.filter(Q(released_at__isnull=True) | Q(released_at__gt=self.assigned_at))
        if self.released_at:
            overlaps = overlaps.filter(assigned_at__lt=self.released_at)
        if overlaps.exists():
            raise ValidationError("Device assignments cannot overlap.")

class CounterEpoch(UUIDPrimaryKeyModel):
    """One reference period of a device counter; values are never summed here."""

    identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    assignment = models.ForeignKey(SessionDevice, on_delete=models.PROTECT, related_name="counter_epochs")
    sensor = models.ForeignKey(Sensor, on_delete=models.PROTECT, related_name="counter_epochs")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="epoch_end_after_start"),
            models.UniqueConstraint(fields=["assignment", "sensor"], condition=Q(ended_at__isnull=True), name="one_open_epoch_per_sensor_assignment"),
        ]

    def clean(self):
        if self.sensor_id and self.assignment_id and self.sensor.device_id != self.assignment.device_id:
            raise ValidationError("Counter sensor must belong to the assigned device.")
        if self.assignment_id and self.started_at:
            if self.started_at < self.assignment.assigned_at or (self.assignment.released_at and self.started_at >= self.assignment.released_at):
                raise ValidationError("Counter epoch must start within the assignment.")
            if self.ended_at and self.assignment.released_at and self.ended_at > self.assignment.released_at:
                raise ValidationError("Counter epoch cannot end after the assignment.")
        if self.assignment_id and self.sensor_id and self.started_at:
            overlaps = CounterEpoch.objects.filter(assignment_id=self.assignment_id, sensor_id=self.sensor_id).exclude(pk=self.pk)
            overlaps = overlaps.filter(Q(ended_at__isnull=True) | Q(ended_at__gt=self.started_at))
            if self.ended_at:
                overlaps = overlaps.filter(started_at__lt=self.ended_at)
            if overlaps.exists():
                raise ValidationError("Counter epochs cannot overlap.")
