"""Explicit Django Admin registrations for monitoring models."""

from django.contrib import admin

from .models import (
    AnalysisResult,
    CounterEpoch,
    Device,
    DeviceCredential,
    ECGSample,
    Measurement,
    MonitoringSession,
    Participant,
    Sensor,
    SensorCapability,
    SessionDevice,
    TelemetryPacket,
)


class ImmutableAfterCreationAdmin(admin.ModelAdmin):
    """Keep accepted records visible without allowing edits or deletion."""

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("pseudonym", "created_at")
    search_fields = ("pseudonym",)
    readonly_fields = ("created_at",)


class MonitoringSessionAdmin(admin.ModelAdmin):
    list_display = ("identifier", "participant", "started_at", "ended_at", "gravity_context")
    list_filter = ("gravity_context",)
    search_fields = ("identifier", "participant__pseudonym")
    filter_horizontal = ("authorized_users",)


class DeviceAdmin(admin.ModelAdmin):
    list_display = ("identifier", "kind", "source", "is_active", "firmware_version")
    list_filter = ("kind", "source", "is_active")
    search_fields = ("identifier",)


class DeviceCredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "is_active", "created_at")
    list_filter = ("is_active",)
    fields = ("device", "is_active", "created_at")
    readonly_fields = ("device", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SensorAdmin(admin.ModelAdmin):
    list_display = ("identifier", "device", "channel", "profile_version", "is_active")
    list_filter = ("is_active", "device__source")
    search_fields = ("identifier", "device__identifier", "channel")


class SensorCapabilityAdmin(admin.ModelAdmin):
    list_display = ("sensor", "metric", "unit", "enabled")
    list_filter = ("metric", "enabled")
    search_fields = ("sensor__identifier",)


class SessionDeviceAdmin(admin.ModelAdmin):
    list_display = ("session", "device", "assigned_at", "released_at")
    search_fields = ("session__identifier", "device__identifier")


class CounterEpochAdmin(admin.ModelAdmin):
    list_display = ("identifier", "assignment", "sensor", "started_at", "ended_at", "reference")
    search_fields = ("identifier", "sensor__identifier", "assignment__session__identifier")


class TelemetryPacketAdmin(ImmutableAfterCreationAdmin):
    list_display = ("packet_id", "device", "assignment", "observed_at", "received_at", "source")
    list_filter = ("source", "schema_version")
    search_fields = ("packet_id", "device__identifier", "assignment__session__identifier")
    readonly_fields = ("received_at",)


class MeasurementAdmin(ImmutableAfterCreationAdmin):
    list_display = ("packet", "sensor", "metric", "value", "unit", "quality")
    list_filter = ("metric", "quality")
    search_fields = ("packet__packet_id", "sensor__identifier")


class ECGSampleAdmin(ImmutableAfterCreationAdmin):
    list_display = ("packet", "sensor", "channel", "sample_index", "observed_at", "amplitude", "unit")
    search_fields = ("packet__packet_id", "sensor__identifier", "channel")


class AnalysisResultAdmin(ImmutableAfterCreationAdmin):
    list_display = ("session", "kind", "sensor", "input_source", "window_started_at", "window_ended_at")
    list_filter = ("kind", "input_source")
    search_fields = ("session__identifier", "sensor__identifier")
    readonly_fields = ("created_at",)


admin.site.register(Participant, ParticipantAdmin)
admin.site.register(MonitoringSession, MonitoringSessionAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(DeviceCredential, DeviceCredentialAdmin)
admin.site.register(Sensor, SensorAdmin)
admin.site.register(SensorCapability, SensorCapabilityAdmin)
admin.site.register(SessionDevice, SessionDeviceAdmin)
admin.site.register(CounterEpoch, CounterEpochAdmin)
admin.site.register(TelemetryPacket, TelemetryPacketAdmin)
admin.site.register(Measurement, MeasurementAdmin)
admin.site.register(ECGSample, ECGSampleAdmin)
admin.site.register(AnalysisResult, AnalysisResultAdmin)
