"""Create a revocable device secret and reveal it once to the operator."""

import secrets

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from monitoring.models import Device, DeviceCredential


class Command(BaseCommand):
    help = "Issue a device ingestion credential; the secret is displayed only once."

    def add_arguments(self, parser):
        parser.add_argument("device_identifier")
        parser.add_argument("--revoke-existing", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        device = Device.objects.filter(identifier=options["device_identifier"], is_active=True).first()
        if device is None:
            raise CommandError("Active device not found.")
        secret = secrets.token_urlsafe(32)
        if options["revoke_existing"]:
            DeviceCredential.objects.filter(device=device, is_active=True).update(is_active=False)
        credential = DeviceCredential.objects.create(device=device, secret_hash=make_password(secret))
        self.stdout.write(f"Device {device.identifier} credential (store securely; shown once):")
        self.stdout.write(f"{credential.id}:{secret}")
