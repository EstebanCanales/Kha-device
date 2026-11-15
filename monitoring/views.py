"""Small HTTP layer for configuration, ingestion, and authorized history."""

from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.db import IntegrityError, connection
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotAuthenticated, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ia import IAError, describe_engine, run_pipeline

from .analysis import analyze_session, sensor_series
from .authentication import DeviceAuthentication, DeviceRateThrottle
from .models import (
    CounterEpoch,
    Device,
    DeviceCredential,
    Measurement,
    Metric,
    MonitoringSession,
    Participant,
    Sensor,
    SensorCapability,
    SessionDevice,
)
from .serializers import (
    BatchInputSerializer,
    BatchOutputSerializer,
    CounterEpochSerializer,
    DeviceSerializer,
    MeasurementSerializer,
    ParticipantSerializer,
    SensorCapabilitySerializer,
    SensorSerializer,
    SessionDeviceSerializer,
    SessionSerializer,
)
from .services import ingest_batch


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Record is referenced or conflicts with another record."


class PayloadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "JSON body exceeds the configured size limit."


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The summary engine is not available."


class LimitedJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        data = stream.read(settings.TELEMETRY_MAX_BODY_BYTES + 1)
        if len(data) > settings.TELEMETRY_MAX_BODY_BYTES:
            raise PayloadTooLarge()
        return super().parse(BytesIO(data), media_type, parser_context)


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsStaffOrSessionReader(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.method in ("GET", "HEAD", "OPTIONS") or request.user.is_staff


class ConfigurationViewSet(viewsets.ModelViewSet):
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = (IsStaff,)
    pagination_class = PageNumberPagination

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise Conflict() from error

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError as error:
            raise Conflict() from error

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError as error:
            raise Conflict() from error


class ParticipantViewSet(ConfigurationViewSet):
    queryset = Participant.objects.all().order_by("pseudonym")
    serializer_class = ParticipantSerializer


class DeviceViewSet(ConfigurationViewSet):
    queryset = Device.objects.all().order_by("identifier")
    serializer_class = DeviceSerializer


class SensorViewSet(ConfigurationViewSet):
    queryset = Sensor.objects.all().order_by("identifier")
    serializer_class = SensorSerializer


class SensorCapabilityViewSet(ConfigurationViewSet):
    queryset = SensorCapability.objects.all().order_by("sensor__identifier", "metric", "unit")
    serializer_class = SensorCapabilitySerializer

    def perform_destroy(self, instance):
        if Measurement.objects.filter(sensor=instance.sensor, metric=instance.metric, unit=instance.unit).exists():
            raise Conflict("Capability is referenced by historical measurements.")
        super().perform_destroy(instance)


class SessionDeviceViewSet(ConfigurationViewSet):
    queryset = SessionDevice.objects.all().order_by("-assigned_at", "id")
    serializer_class = SessionDeviceSerializer


class CounterEpochViewSet(ConfigurationViewSet):
    queryset = CounterEpoch.objects.all().order_by("-started_at", "id")
    serializer_class = CounterEpochSerializer


class HistoryPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500


def _require_source(request):
    source = request.query_params.get("source")
    if source not in Device.Source.values:
        raise ValidationError({"source": "Choose hardware or simulated explicitly."})
    return source


def _history_filters(request, session):
    source = _require_source(request)
    readings = Measurement.objects.select_related("packet", "sensor", "counter_epoch").filter(
        packet__assignment__session=session, packet__source=source
    )
    metric = request.query_params.get("metric")
    if metric:
        if metric not in Metric.values:
            raise ValidationError({"metric": "Unknown metric."})
        readings = readings.filter(metric=metric)
    sensor = request.query_params.get("sensor")
    if sensor:
        readings = readings.filter(sensor__identifier=sensor)
    bounds = []
    for name, lookup in (("observed_from", "gte"), ("observed_to", "lte")):
        raw = request.query_params.get(name)
        if raw:
            instant = parse_datetime(raw)
            if instant is None or not is_aware(instant):
                raise ValidationError({name: "Use an ISO 8601 timestamp with timezone."})
            readings = readings.filter(**{f"packet__observed_at__{lookup}": instant})
            bounds.append((name, instant))
    if len(bounds) == 2:
        start, end = bounds[0][1], bounds[1][1]
        if end < start or end - start > timedelta(days=31):
            raise ValidationError("Date range must be ordered and at most 31 days.")
    return readings


class SessionViewSet(viewsets.ModelViewSet):
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = (IsStaffOrSessionReader,)
    serializer_class = SessionSerializer
    pagination_class = HistoryPagination

    def get_queryset(self):
        queryset = MonitoringSession.objects.select_related("participant").order_by("-started_at", "id")
        if not self.request.user.is_authenticated:
            return queryset.none()
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(authorized_users=self.request.user)

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise Conflict() from error

    @extend_schema(
        parameters=[
            OpenApiParameter("source", str, required=True, enum=Device.Source.values),
            OpenApiParameter("metric", str), OpenApiParameter("sensor", str),
            OpenApiParameter("observed_from", str), OpenApiParameter("observed_to", str),
        ],
        responses=MeasurementSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def measurements(self, request, pk=None):
        session = self.get_object()
        readings = _history_filters(request, session).order_by("packet__observed_at", "id")
        page = self.paginate_queryset(readings)
        return self.get_paginated_response(MeasurementSerializer(page, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("source", str, required=True, enum=Device.Source.values),
            OpenApiParameter("metric", str), OpenApiParameter("sensor", str),
            OpenApiParameter("observed_from", str), OpenApiParameter("observed_to", str),
        ],
        responses=MeasurementSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def latest(self, request, pk=None):
        session = self.get_object()
        readings = _history_filters(request, session).order_by("-packet__observed_at", "-id")
        latest = []
        seen = set()
        for reading in readings:
            key = (reading.sensor_id, reading.metric, reading.unit, reading.counter_epoch_id)
            if key not in seen:
                seen.add(key)
                latest.append(reading)
        page = self.paginate_queryset(latest)
        return self.get_paginated_response(MeasurementSerializer(page, many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter("source", str, required=True, enum=Device.Source.values)],
        responses=dict,
    )
    @action(detail=True, methods=["get"])
    def analysis(self, request, pk=None):
        """Personal baseline, changes from it, dose counters, and data gaps. Descriptive, not diagnostic."""
        return Response(analyze_session(self.get_object(), _require_source(request)))

    @extend_schema(
        parameters=[OpenApiParameter("source", str, required=True, enum=Device.Source.values)],
        responses=dict,
    )
    @action(detail=True, methods=["get"])
    def overview(self, request, pk=None):
        """Everything the dashboard needs in one request: analysis, per-sensor series, and the AI engine in use."""
        session = self.get_object()
        source = _require_source(request)
        return Response({
            "session": {"id": str(session.pk), "identifier": session.identifier},
            "analysis": analyze_session(session, source),
            "sensors": sensor_series(session, source),
            "ia": describe_engine(),
        })

    @extend_schema(
        parameters=[OpenApiParameter("source", str, required=True, enum=Device.Source.values)],
        request=None, responses=dict,
    )
    @action(detail=True, methods=["post"], permission_classes=(IsAuthenticated,))
    def summary(self, request, pk=None):
        """Run the specialists and the synthesis. Readers of the session may call it; it stores nothing."""
        analysis = analyze_session(self.get_object(), _require_source(request))
        try:
            result = run_pipeline(analysis)
        except IAError as error:
            raise ServiceUnavailable(str(error)) from error
        return Response({"analysis": analysis, **result})


class TelemetryBatchView(APIView):
    authentication_classes = (DeviceAuthentication,)
    permission_classes = ()
    parser_classes = (LimitedJSONParser,)
    throttle_classes = (DeviceRateThrottle,)

    @extend_schema(request=BatchInputSerializer, responses={200: BatchOutputSerializer, 201: BatchOutputSerializer})
    def post(self, request):
        if not isinstance(request.auth, DeviceCredential):
            raise NotAuthenticated("Device credentials are required.")
        serializer = BatchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_batch(serializer.validated_data, request.auth)
        return Response(result, status=status.HTTP_201_CREATED if result["inserted"] else status.HTTP_200_OK)


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
