"""Shared metric vocabulary, units, and UUID model base."""

import uuid

from django.db import models


class Metric(models.TextChoices):
    HEART_RATE = "heart_rate", "Heart rate"
    PULSE_RATE = "pulse_rate", "Pulse rate"
    ECG = "ecg", "ECG signal"
    RESPIRATORY_RATE = "respiratory_rate", "Respiratory rate"
    SPO2 = "spo2", "Peripheral oxygen saturation estimate"
    SKIN_TEMPERATURE = "skin_temperature", "Skin temperature"
    ACCELERATION_X = "acceleration_x", "Acceleration X"
    ACCELERATION_Y = "acceleration_y", "Acceleration Y"
    ACCELERATION_Z = "acceleration_z", "Acceleration Z"
    ABSORBED_DOSE_RATE = "absorbed_dose_rate", "Absorbed dose rate"
    EQUIVALENT_DOSE_RATE = "equivalent_dose_rate", "Equivalent dose rate"
    PERSONAL_DOSE_EQUIVALENT_RATE = "personal_dose_equivalent_rate", "Personal dose equivalent rate"
    ABSORBED_DOSE_CUMULATIVE = "absorbed_dose_cumulative", "Cumulative absorbed dose"
    EQUIVALENT_DOSE_CUMULATIVE = "equivalent_dose_cumulative", "Cumulative equivalent dose"
    PERSONAL_DOSE_EQUIVALENT_CUMULATIVE = "personal_dose_equivalent_cumulative", "Cumulative personal dose equivalent"
    MEASUREMENT_INTERVAL = "measurement_interval", "Interval between readings"
    MISSION_ELAPSED_TIME = "mission_elapsed_time", "Time since mission start"
    INTERNAL_TEMPERATURE = "internal_temperature", "Internal circuit temperature"
    DIS_CHAMBER_STATUS = "dis_chamber_status", "DIS chamber status"
    STORAGE_STATUS = "storage_status", "Storage status"
    DOSE_RATE_INCREASE = "dose_rate_increase", "Dose rate increased since previous valid sample"
    EXPOSURE_DURATION = "exposure_duration", "Recorded exposure duration"


METRIC_UNITS = {
    Metric.HEART_RATE: {"bpm"},
    Metric.PULSE_RATE: {"bpm"},
    Metric.ECG: {"uV", "mV"},
    Metric.RESPIRATORY_RATE: {"breaths/min"},
    Metric.SPO2: {"%"},
    Metric.SKIN_TEMPERATURE: {"degC"},
    Metric.ACCELERATION_X: {"m/s2"},
    Metric.ACCELERATION_Y: {"m/s2"},
    Metric.ACCELERATION_Z: {"m/s2"},
    Metric.ABSORBED_DOSE_RATE: {"Gy/h", "mGy/h", "uGy/h", "uGy/min"},
    Metric.EQUIVALENT_DOSE_RATE: {"Sv/h", "mSv/h", "uSv/h"},
    Metric.PERSONAL_DOSE_EQUIVALENT_RATE: {"Sv/h", "mSv/h", "uSv/h"},
    Metric.ABSORBED_DOSE_CUMULATIVE: {"Gy", "mGy", "uGy"},
    Metric.EQUIVALENT_DOSE_CUMULATIVE: {"Sv", "mSv", "uSv"},
    Metric.PERSONAL_DOSE_EQUIVALENT_CUMULATIVE: {"Sv", "mSv", "uSv"},
    Metric.EXPOSURE_DURATION: {"s"},
    Metric.MEASUREMENT_INTERVAL: {"s"},
    Metric.MISSION_ELAPSED_TIME: {"s"},
    Metric.INTERNAL_TEMPERATURE: {"degC"},
    Metric.DIS_CHAMBER_STATUS: {"code"},
    Metric.STORAGE_STATUS: {"code"},
    Metric.DOSE_RATE_INCREASE: {"1"},
}
CUMULATIVE_METRICS = {
    Metric.ABSORBED_DOSE_CUMULATIVE,
    Metric.EQUIVALENT_DOSE_CUMULATIVE,
    Metric.PERSONAL_DOSE_EQUIVALENT_CUMULATIVE,
}


class UUIDPrimaryKeyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
