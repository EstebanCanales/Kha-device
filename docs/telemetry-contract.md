# Contrato de telemetría v1

El transporte inicial es HTTP/JSON. Una credencial de dispositivo se presenta como `Authorization: Device <credential_uuid>:<secret>` y solo permite `POST /api/v1/telemetry/batches/`. La credencial se genera con `provision_device_token`, se guarda con el hasher de contraseñas de Django y se puede revocar individualmente.

## Identidades y estructura

- `packet_id`: UUID generado por el emisor antes del primer envío; se conserva al reintentar.
- `device_id`, `session_id`, `sensor_id`: identificadores legibles y estables (`Device.identifier`, `MonitoringSession.identifier`, `Sensor.identifier`), no las claves primarias UUID internas.
- `counter_epoch`: UUID público `CounterEpoch.identifier` para contadores acumulados; no es la clave primaria de esa fila.
- Las lecturas de un paquete comparten `observed_at`. Capturas hechas en momentos distintos requieren paquetes distintos.

Ejemplo sintético con identificadores creados por `seed_demo` (ajuste `observed_at` a un momento dentro de la sesión al enviarlo):

```json
{
  "schema_version": 1,
  "packets": [
    {
      "packet_id": "27980ce0-91a0-4b41-9ed8-89f0a34cc4c4",
      "device_id": "harness-sim-001",
      "session_id": "session-demo-001",
      "observed_at": "2026-11-14T20:00:00Z",
      "source": "simulated",
      "readings": [
        {"sensor_id": "hr-sim-001", "metric": "heart_rate", "value": "78.0", "unit": "bpm", "quality": "valid"}
      ]
    }
  ]
}
```

El emisor solo puede enviar por su dispositivo. La sesión se resuelve mediante `SessionDevice` y el instante de medición; no se acepta un `participant_id` aportado por el dispositivo. `source` debe coincidir con el perfil registrado (`simulated` o `hardware`). Cada sensor debe pertenecer al dispositivo, estar activo y tener habilitada la combinación exacta de métrica y unidad.

## Valores, tiempo y calidad

Los valores escalares son **cadenas decimales finitas**, hasta 18 dígitos enteros y 12 decimales. `NaN`, infinito, exponentes, campos desconocidos y precisión superior se rechazan. `quality` admite `valid`, `unreliable` y `missing`; solo `missing` exige `value: null`. La ausencia nunca se convierte en cero. Un vector de aceleración se envía como tres lecturas escalares `acceleration_x`, `acceleration_y` y `acceleration_z`, con el marco de referencia configurado en cada sensor. No se infiere gravedad a partir de esas lecturas.

`observed_at` requiere zona horaria y se normaliza a UTC. `received_at` lo genera el servidor. Se admiten paquetes retrasados y fuera de orden mientras su instante pertenezca a la sesión y asignación históricas. La tolerancia futura se configura con `TELEMETRY_FUTURE_SKEW_SECONDS` (300 por defecto); no hay sustitución automática de tiempos ni límite de antigüedad adicional. Un paquete sin tiempo confiable se rechaza.

Las dosis absorbidas usan Gy, mGy o uGy; las equivalentes y personales usan Sv, mSv o uSv. Las tasas usan los mismos prefijos por hora. La unidad original se guarda sin conversión. Los contadores acumulados requieren una época y no se suman entre sí. `exposure_duration` registra segundos reportados por el instrumento o protocolo, no tiempo entre peticiones. Las combinaciones admitidas están en `METRIC_UNITS`; ninguna está habilitada en un dispositivo hasta crear `SensorCapability(enabled=True)`.

## Lotes, reenvíos y límites

Un lote contiene 1 a 100 paquetes, cada uno con 1 a 32 lecturas. El cuerpo JSON se limita a 262144 bytes por defecto y la ingesta a 120 peticiones por minuto y credencial en la caché local de Django. Para un despliegue con varios procesos hace falta una caché compartida. El lote es atómico: cualquier paquete nuevo inválido revierte todos los insertados en esa petición.

La unicidad `(device, packet_id)` se impone en la base de datos. Para comparar reenvíos se calcula SHA-256 de una representación JSON canónica que incluye versión, dispositivo, sesión, instante UTC, procedencia y todas las lecturas. Las lecturas se ordenan por sensor y métrica; los decimales se normalizan matemáticamente, y los campos opcionales ausentes toman su valor vacío o nulo. Se excluyen el ID interno y los campos generados por el servidor. Un reenvío idéntico devuelve `duplicate`; reutilizar el mismo `packet_id` con contenido distinto devuelve `409`. El cliente debe conservar el mismo cuerpo e identidad al reintentar fallos temporales y esperar cada vez más tiempo, como hace el simulador.

Respuesta con inserciones (`201`) o solo duplicados (`200`):

```json
{
  "packets": [{"packet_id": "27980ce0-91a0-4b41-9ed8-89f0a34cc4c4", "status": "inserted"}],
  "inserted": 1,
  "duplicates": 0
}
```

`400` indica contrato o medición inválida; `401` credencial ausente, inválida o revocada; `403` dispositivo o sesión no autorizados; `409` identidad reutilizada con otro contenido; `413` cuerpo excesivo; `429` frecuencia excesiva. Un error `5xx` o fallo de conexión es temporal y debe reintentarse con la misma identidad. `/readyz/` responde `503` cuando no puede consultar la base de datos.

## Consulta

`GET /api/v1/sessions/` lista solo sesiones autorizadas para la cuenta humana; el personal administrativo puede ver todas. `GET /api/v1/sessions/{uuid}/measurements/` devuelve historial paginado (100 filas por defecto, máximo 500 por página) en orden estable de `observed_at` e ID. `GET /api/v1/sessions/{uuid}/latest/` devuelve la última lectura por sensor, métrica, unidad y época, según `observed_at`; incluye su tiempo y no declara que siga vigente.

Ambas consultas de lecturas requieren `source=hardware` o `source=simulated`. Admiten `metric`, `sensor` (identificador legible), `observed_from` y `observed_to` con zona horaria. Si se aportan ambos tiempos, el intervalo máximo es de 31 días. La respuesta incluye valor, unidad, calidad, procedencia, `observed_at`, `received_at` y versión de perfil. Las lecturas aceptadas no tienen endpoints genéricos de edición ni borrado.

## Dosimeter extension

The synthetic `dosimeter-demo.v1` profile adds `measurement_interval` and `mission_elapsed_time` (`s`), `internal_temperature` (`degC`), `dis_chamber_status` and `storage_status` (`code`: 0 unknown, 1 ok, 2 fault), and `dose_rate_increase` (`1`: 0 false, 1 true). Missing values remain null. Elapsed timing values cannot be negative. Absorbed dose rate also accepts `uGy/min`; no automatic conversion occurs. See [dosimeter guide](dosimeter.md) for exact meanings, configuration, replay, and hardware limitations. Batch schema version remains 1; the sensor profile records the extension version.
