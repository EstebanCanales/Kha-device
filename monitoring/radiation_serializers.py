"""Query and response schemas for NASA radiation context."""

from rest_framework import serializers

from .nasa_radiation import validate_window
from .serializers import StrictSerializer


class RadiationQuerySerializer(StrictSerializer):
    start_date = serializers.CharField()
    end_date = serializers.CharField()

    def validate(self, data):
        try:
            validate_window(data["start_date"], data["end_date"])
        except ValueError as error:
            raise serializers.ValidationError(str(error)) from None
        return data


class RadiationContextSerializer(serializers.Serializer):
    schema_version = serializers.CharField()
    source = serializers.CharField()
    event_type = serializers.CharField()
    source_url = serializers.URLField()
    fetched_at = serializers.DateTimeField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    personal_dose_available = serializers.BooleanField()
    event_count = serializers.IntegerField()
    events = serializers.ListField(child=serializers.DictField())
    note = serializers.CharField()
