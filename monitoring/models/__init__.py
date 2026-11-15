"""Domain model registry. Import public model names from ``monitoring.models``."""

# Import in dependency order so Django registers every model during app loading.
from .analysis import AnalysisResult
from .assignments import CounterEpoch, SessionDevice
from .participants import MonitoringSession, Participant
from .sensors import Device, DeviceCredential, Sensor, SensorCapability
from .shared import CUMULATIVE_METRICS, METRIC_UNITS, Metric, UUIDPrimaryKeyModel
from .telemetry import ECGSample, Measurement, TelemetryPacket

__all__ = [
    "AnalysisResult", "CounterEpoch", "CUMULATIVE_METRICS", "Device",
    "DeviceCredential", "ECGSample", "Measurement", "METRIC_UNITS",
    "Metric", "MonitoringSession", "Participant", "Sensor",
    "SensorCapability", "SessionDevice", "TelemetryPacket",
    "UUIDPrimaryKeyModel",
]
