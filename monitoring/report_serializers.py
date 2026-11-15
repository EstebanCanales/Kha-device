"""Versioned report inputs and outputs for future model consumers."""

from datetime import timedelta

from rest_framework import serializers

from .models import Device
from .serializers import AwareDateTimeField, MeasurementSerializer, StrictSerializer


class ReportQuerySerializer(StrictSerializer):
    source = serializers.ChoiceField(choices=Device.Source.choices)
    observed_from = AwareDateTimeField()
    observed_to = AwareDateTimeField()
    output = serializers.ChoiceField(choices=["json", "text"], default="json")

    def validate(self, data):
        duration = data["observed_to"] - data["observed_from"]
        if not timedelta(0) < duration <= timedelta(days=31):
            raise serializers.ValidationError("Report window must be positive and at most 31 days.")
        return data


class ReportSessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    participant_id = serializers.UUIDField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    gravity_context = serializers.CharField()


class ReportWindowSerializer(serializers.Serializer):
    observed_from = serializers.DateTimeField()
    observed_to = serializers.DateTimeField()
    bounds = serializers.CharField()


REPORT_CATEGORIES = ["vital_signs", "body_temperature", "dosimeter"]


class TaggedMeasurementSerializer(MeasurementSerializer):
    category = serializers.ChoiceField(choices=REPORT_CATEGORIES, read_only=True)

    class Meta(MeasurementSerializer.Meta):
        fields = (*MeasurementSerializer.Meta.fields, "category")


class ReportSeriesSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=REPORT_CATEGORIES)
    device_id = serializers.CharField()
    sensor_id = serializers.CharField()
    metric = serializers.CharField()
    unit = serializers.CharField()
    profile_version = serializers.CharField()
    method = serializers.CharField()
    method_version = serializers.CharField()
    counter_epoch = serializers.UUIDField(allow_null=True)
    quality_counts = serializers.DictField(child=serializers.IntegerField())
    latest = TaggedMeasurementSerializer()
    readings = TaggedMeasurementSerializer(many=True)


class ReportDomainSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["available", "no_data"])
    measurement_count = serializers.IntegerField()
    series = ReportSeriesSerializer(many=True)


class ReportDomainsSerializer(serializers.Serializer):
    vital_signs = ReportDomainSerializer()
    body_temperature = ReportDomainSerializer()
    dosimeter = ReportDomainSerializer()


class CombinedReportSerializer(serializers.Serializer):
    schema_version = serializers.CharField()
    generated_at = serializers.DateTimeField()
    source = serializers.ChoiceField(choices=Device.Source.choices)
    session = ReportSessionSerializer()
    window = ReportWindowSerializer()
    measurement_count = serializers.IntegerField()
    missing_domains = serializers.ListField(child=serializers.CharField())
    notes = serializers.ListField(child=serializers.CharField())
    domains = ReportDomainsSerializer()
