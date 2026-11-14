"""Synthetic channels only; status codes are not a DIS instrument protocol."""

DEVICE_ID = "dosimeter-detail-sim-001"
PROFILE_VERSION = "dosimeter-demo.v1"
CHANNELS = {
    "absorbed_dose_rate": "uGy/h",
    "absorbed_dose_cumulative": "uGy",
    "exposure_duration": "s",
    "measurement_interval": "s",
    "mission_elapsed_time": "s",
    "internal_temperature": "degC",
    "dis_chamber_status": "code",
    "storage_status": "code",
    "dose_rate_increase": "1",
}
