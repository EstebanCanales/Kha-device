"""Participant identities and monitoring session context."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .shared import UUIDPrimaryKeyModel


class Participant(UUIDPrimaryKeyModel):
    pseudonym = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.pseudonym

class MonitoringSession(UUIDPrimaryKeyModel):
    class Gravity(models.TextChoices):
        EARTH = "earth", "Earth"
        MICRO = "microgravity", "Microgravity"
        PARTIAL = "partial", "Partial gravity"
        HYPER = "hypergravity", "Hypergravity"
        UNKNOWN = "unknown", "Unknown"

    identifier = models.CharField(max_length=80, unique=True)
    participant = models.ForeignKey(Participant, on_delete=models.PROTECT, related_name="sessions")
    authorized_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="monitoring_sessions")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    gravity_context = models.CharField(max_length=20, choices=Gravity, default=Gravity.UNKNOWN)
    gravity_context_source = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="session_end_after_start")]

    def __str__(self):
        return self.identifier
