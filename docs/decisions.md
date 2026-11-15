# Decisiones provisionales

- El backend es un monolito Django/DRF. SQLite permite demostración local; `DB_ENGINE=postgresql` usa PostgreSQL con `psycopg`. No se verificó PostgreSQL en este entorno porque no había un servidor disponible.
- La configuración usa CRUD para participantes, sesiones, dispositivos, sensores, capacidades, asignaciones y épocas de contador. La ingesta crea paquetes y mediciones; el historial es de solo lectura. ECG crudo y resultados derivados continúan como modelos sin API de adquisición o análisis.
- Las claves primarias de `monitoring` son UUID v4. Los identificadores legibles se mantienen para contratos de dispositivo. Los usuarios de Django conservan las claves propias del framework.
- Cada dispositivo tiene credenciales revocables y verificadores con el hasher de Django. No se almacena el secreto recuperable. La rotación puede emitir una nueva credencial y revocar las anteriores.
- La lista de métricas representa posibilidades de almacenamiento. Solo `seed_demo` habilita perfiles **simulados**. No hay compatibilidad comprobada con hardware.
- No se calculan diagnósticos, alertas, riesgo radiológico, totales personales ni actividad a partir de aceleración. La retención y el borrado automático quedan pendientes.
- Se acepta telemetría atrasada dentro de la asignación temporal sin límite adicional de antigüedad. El futuro se limita por tolerancia configurable. La sincronización de relojes y política de datos sin tiempo confiable requieren especificación de hardware.
- La limitación de peticiones usa caché local y sirve para un proceso de desarrollo. Un despliegue con varios procesos necesita una caché compartida y pruebas de carga.
- El contrato v1 conserva magnitudes y unidades originales. La procedencia y la época de contador evitan mezclar datos de simulación o referencias de dosis distintas.

Pendiente antes de integrar equipos reales: modelos y fichas técnicas, magnitudes y calibración del dosímetro, payload y protocolo, frecuencia de muestreo, reloj y almacenamiento durante desconexiones, procedimiento de reasignación y reinicio, fuente del contexto de gravedad, retención, autorización operativa y entorno de despliegue.

## Dedicated dosimeter prototype

- Reuse the batch API, device credentials, session authorization, read-only history, and counter epochs; no additional ingestion endpoint is needed.
- Use a separate `dosimeter-detail-sim-001` profile so existing demo sensor configuration is preserved.
- Store status as explicitly documented application codes and elapsed times as decimal seconds. DIS state is aggregate until the chamber inventory and protocol are known.
- Use a durable SQLite desktop journal as a storage adapter stand-in. It is not FRAM hardware support. Preserve records and identities through acknowledgment and replay; retention remains pending.
- Synthetic cumulative increments are independent fixtures, not inferred from rates. A rate-increase flag compares adjacent valid captures only and has no radiological-risk meaning.

## Combined reports

- Generate bounded JSON/text reports on demand from both acquisition streams within one authorized session and source. No additional database tables, model calls, inference, external delivery, or scheduled jobs.
- Require explicit start/end timestamps; use half-open windows for adjacent report exports. Reject oversized reports instead of hiding readings from a model through truncation.
- Preserve per-reading evidence and quality, and group different units, epochs, methods, and profiles separately. No synthetic time alignment or cumulative-dose totals.
- Internal report consumers must supply an active authorized Django user. Reports omit names/pseudonyms and credentials. Stored report retention and downstream model token budgets remain caller responsibilities.

- Combined report v2 separates `body_temperature` from `vital_signs`, tags every series/reading/latest observation, and returns one JSON attachment by default. Internal circuit temperature remains dosimeter telemetry. Existing data and ingestion contracts do not change.
