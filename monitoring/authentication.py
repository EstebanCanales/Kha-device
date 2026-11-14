"""Device-only authentication for telemetry ingestion."""

import uuid

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.throttling import SimpleRateThrottle

from .models import DeviceCredential


class DeviceAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header:
            return None
        if not header.startswith("Device "):
            raise AuthenticationFailed("Device credentials are required.")
        try:
            credential_id, secret = header[7:].split(":", 1)
            credential_id = uuid.UUID(credential_id)
        except (ValueError, TypeError) as error:
            raise AuthenticationFailed("Invalid device credential format.") from error
        credential = DeviceCredential.objects.select_related("device").filter(pk=credential_id, is_active=True, device__is_active=True).first()
        if credential is None or not check_password(secret, credential.secret_hash):
            raise AuthenticationFailed("Invalid or revoked device credential.")
        return (AnonymousUser(), credential)

    def authenticate_header(self, request):
        return "Device"


class DeviceRateThrottle(SimpleRateThrottle):
    scope = "telemetry"

    def get_cache_key(self, request, view):
        if not isinstance(request.auth, DeviceCredential):
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(request.auth.pk)}
