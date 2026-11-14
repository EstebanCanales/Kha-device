#!/usr/bin/env python3
"""Simulador parcial MAX30205 -> JSON, sin dependencias externas (Python 3.9+).

Fuente: MAX30205.pdf adjunto, pp. 8 y 10-13.
Modela temperatura de 0 a 50 C, registro 0x00 de 16 bits (complemento a dos,
MSB primero, 1/256 C por unidad) y alarma OS en modo comparador activo bajo,
con fault queue de 1 conversion. THYST/TOS se cuantizan tambien a 1/256 C.
Conserva los umbrales iniciales documentados: THYST=75 C y TOS=80 C.
Para probar la alarma dentro del rango operativo, configura otros umbrales.

Cada llamada a sample() representa una conversion terminada. No emula el bus
I2C, tiempos de conversion, registro de configuracion, modo extendido,
interrupciones, shutdown ni one-shot. No modela fisiologia ni transferencia
termica: el chip real mide su propia temperatura. El ruido opcional es una
perturbacion sintetica elegida por el usuario, no un modelo de exactitud.
El redondeo al codigo mas cercano es una aproximacion de cuantizacion.
Los timestamps, identificadores y el JSON pertenecen al software.

Ejemplos:
  python3 simulador_max30205.py --temperature 36.5 --output lectura.json
  python3 simulador_max30205.py --temperature 36.5 --samples 10 --noise 0.02
  python3 simulador_max30205.py --values 36.5,38.25,37.75,37.25 \
      --tos 38 --thyst 37.5 --output prueba_alarma.json

--interval separa timestamps virtuales; el programa no espera tiempo real.
--values determina el numero de muestras y sustituye --samples.
Para resultados repetibles, utiliza --seed y --start con una fecha ISO 8601
que incluya zona horaria, por ejemplo 2026-11-14T12:00:00Z.

Uso desde otro modulo:
  sensor = MAX30205Simulator(tos_c=38, thyst_c=37.5)
  lectura = sensor.sample(36.5)
  texto_json = json.dumps(lectura, allow_nan=False)
"""

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LSB_C = 1 / 256


def encode_temperature(temperature_c):
    """Devuelve los dos bytes de una temperatura dentro del rango operativo."""
    if not math.isfinite(temperature_c) or not 0 <= temperature_c <= 50:
        raise ValueError("La temperatura debe ser finita y estar entre 0 y 50 C.")
    raw = round(temperature_c * 256)
    return raw.to_bytes(2, byteorder="big", signed=True)


def decode_temperature(data):
    """Decodifica dos bytes del formato normal; no aplica el offset extendido."""
    if not isinstance(data, (bytes, bytearray)) or len(data) != 2:
        raise ValueError("Se necesitan exactamente dos bytes, MSB primero.")
    return int.from_bytes(data, byteorder="big", signed=True) * LSB_C


class MAX30205Simulator:
    """Modelo de conversiones terminadas y alarma comparadora con memoria."""

    def __init__(self, tos_c=80.0, thyst_c=75.0, sensor_id="max30205-sim-001"):
        for value in (tos_c, thyst_c):
            if not math.isfinite(value) or not 0 <= value <= 127.99609375:
                raise ValueError("Los umbrales deben estar entre 0 y 127.99609375 C.")
        self.tos_c = round(tos_c * 256) * LSB_C
        self.thyst_c = round(thyst_c * 256) * LSB_C
        if self.thyst_c >= self.tos_c:
            raise ValueError("THYST debe ser menor que TOS despues de cuantizar.")
        self.sensor_id = sensor_id
        self.os_asserted = False

    def sample(self, temperature_c, timestamp=None):
        """Toma una conversion sintetica; conserva OS entre llamadas."""
        data = encode_temperature(temperature_c)
        measured = decode_temperature(data)
        # Por encima de TOS activa; por debajo de THYST desactiva.
        # Entre ambos umbrales, incluida la igualdad, conserva su estado.
        if measured > self.tos_c:
            self.os_asserted = True
        elif measured < self.thyst_c:
            self.os_asserted = False
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("El timestamp debe incluir una zona horaria.")
        return {
            "simulated": True,
            "sensor": "MAX30205",
            "sensor_id": self.sensor_id,
            "timestamp": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "temperature_c": measured,
            "raw_value": int.from_bytes(data, "big", signed=True),
            "raw_hex": "0x" + data.hex().upper(),
            "raw_bytes": list(data),
            "os_asserted": self.os_asserted,
            # Nivel logico con un pull-up externo, porque OS es open-drain.
            "os_pin_level_with_pullup": 0 if self.os_asserted else 1,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--temperature", type=float, default=36.5, help="Temperatura constante, en C.")
    source.add_argument("--values", help="Secuencia de temperaturas separadas por comas.")
    parser.add_argument("--samples", type=int, default=1, help="Cantidad para --temperature.")
    parser.add_argument("--interval", type=float, default=1.0, help="Segundos entre timestamps virtuales.")
    parser.add_argument("--noise", type=float, default=0.0, help="Desviacion estandar de ruido sintetico, C.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla del ruido reproducible.")
    parser.add_argument("--tos", type=float, default=80.0, help="Umbral superior; valor inicial del chip: 80 C.")
    parser.add_argument("--thyst", type=float, default=75.0, help="Umbral inferior; valor inicial del chip: 75 C.")
    parser.add_argument("--start", help="Fecha ISO 8601 con zona horaria; por defecto ahora en UTC.")
    parser.add_argument("--output", type=Path, help="Escribe el JSON aqui; si se omite, usa stdout.")
    args = parser.parse_args(argv)
    try:
        if args.samples < 1:
            raise ValueError("--samples debe ser mayor que cero.")
        if not math.isfinite(args.interval) or args.interval <= 0:
            raise ValueError("--interval debe ser finito y mayor que cero.")
        if not math.isfinite(args.noise) or args.noise < 0:
            raise ValueError("--noise debe ser finito y no negativo.")
        values = [float(v.strip()) for v in args.values.split(",")] if args.values is not None else [args.temperature] * args.samples
        for value in values:
            encode_temperature(value)
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00")) if args.start else datetime.now(timezone.utc)
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("--start debe incluir zona horaria, por ejemplo Z o -06:00.")
        sensor = MAX30205Simulator(args.tos, args.thyst)
        rng = random.Random(args.seed)
        readings = []
        for i, value in enumerate(values):
            perturbed = value + rng.gauss(0.0, args.noise) if args.noise else value
            # Se rechazan temperaturas fuera de rango, no se recortan silenciosamente.
            readings.append(sensor.sample(perturbed, start + timedelta(seconds=i * args.interval)))
        payload = {
            "schema_version": 1,
            "simulated": True,
            "configuration": {
                "data_format": "normal",
                "os_mode": "comparator",
                "os_active_level": 0,
                "fault_queue": 1,
                "tos_c": sensor.tos_c,
                "thyst_c": sensor.thyst_c,
                "resolution_c": LSB_C,
            },
            "simulation": {
                "interval_s": args.interval,
                "noise_stddev_c": args.noise,
                "seed": args.seed,
                "time_mode": "virtual",
            },
            "samples": readings,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
            print(f"JSON guardado: {args.output}", file=sys.stderr)
        else:
            print(text, end="")
        return 0
    except (ValueError, OverflowError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
