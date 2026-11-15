"""Everything needed to open the dashboard with data, in one command (local demo only)."""

import secrets
import uuid
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from monitoring.demo_data import CAD, VITALS, generate
from monitoring.models import Device, DeviceCredential, Measurement, MonitoringSession
from monitoring.serializers import BatchInputSerializer
from monitoring.services import ingest_batch

BATCH = 100  # packets per ingest call, the same limit as the HTTP endpoint


class Command(BaseCommand):
    help = "Apply migrations, create a demo user, register the Kha-device 01 profiles, and load simulated data."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", help="Password for a NEW user; generated and shown once if omitted")
        parser.add_argument("--minutes", type=int, default=60, help="History to generate, ending now")
        parser.add_argument("--scenario", choices=("stress", "baseline"), default="stress")
        parser.add_argument("--seed", type=int, default=1)
        parser.add_argument("--more", action="store_true", help="Add another window even if simulated data already exists")

    def handle(self, *args, **options):
        out = self.stdout
        call_command("migrate", verbosity=0, interactive=False)

        username = options["username"]
        user, created = get_user_model().objects.get_or_create(username=username)
        password = None
        if created:
            password = options["password"] or secrets.token_urlsafe(9)
            user.set_password(password)
            user.save()

        setup = StringIO()
        call_command("setup_kha_devices", reader=username, stdout=setup)
        info = dict(line.split("=", 1) for line in setup.getvalue().splitlines() if "=" in line)
        session = MonitoringSession.objects.get(identifier=info["session_identifier"])

        has_data = Measurement.objects.filter(packet__assignment__session=session, packet__source="simulated").exists()
        if has_data and not options["more"]:
            out.write("La sesión ya tiene datos simulados; no se agregan más (usa --more para sumar otra ventana).")
        else:
            start = timezone.now().replace(microsecond=0) - timedelta(minutes=options["minutes"])
            samples = options["minutes"] * 2  # one sample every 30 s
            # A second run must not collide with the first one's packets.
            seed = options["seed"] + (Measurement.objects.count() % 1000 if has_data else 0)
            sent = {CAD: [], VITALS: []}
            for at, vitals, cad in generate(
                start, samples, 30, seed, options["scenario"], 0.02, info["epoch_high"], info["epoch_low"]
            ):
                for device_id, readings in ((VITALS, vitals), (CAD, cad)):
                    packet_id = uuid.uuid5(uuid.NAMESPACE_URL, f"kha-sim:{seed}:{device_id}:{at.isoformat()}")
                    sent[device_id].append({
                        "packet_id": str(packet_id), "device_id": device_id, "session_id": session.identifier,
                        "observed_at": at.isoformat(), "source": "simulated", "readings": readings,
                    })
            stored = 0
            for device_id, packets in sent.items():
                # No credential is stored: ingestion only needs to know which device sends.
                credential = DeviceCredential(device=Device.objects.get(identifier=device_id))
                for i in range(0, len(packets), BATCH):
                    batch = BatchInputSerializer(data={"schema_version": 1, "packets": packets[i : i + BATCH]})
                    batch.is_valid(raise_exception=True)
                    stored += ingest_batch(batch.validated_data, credential)["inserted"]
            out.write(f"Se cargaron {stored} paquetes simulados ({options['scenario']}, {options['minutes']} min).")

        out.write("")
        out.write(self.style.SUCCESS("Listo. Ahora arranca el servidor y abre la app:"))
        out.write("  uv run python manage.py runserver")
        out.write("  http://127.0.0.1:8000/app/")
        out.write("")
        if created:
            out.write(f"  Usuario:    {username}")
            out.write(f"  Contraseña: {password}   (solo se muestra esta vez; guárdala)")
        else:
            out.write(f"  El usuario «{username}» ya existía: su contraseña no se cambió.")
