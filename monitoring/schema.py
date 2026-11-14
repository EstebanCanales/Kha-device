"""OpenAPI description for the device-only credential header."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class DeviceAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "monitoring.authentication.DeviceAuthentication"
    name = "DeviceCredential"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Device <credential_uuid>:<secret>; available only for telemetry ingestion.",
        }
