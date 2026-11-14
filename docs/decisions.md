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

## Temperature integration

The vital-signs generator uses `MAX30205Simulator.sample()` from `monitoring/body_temperature.py` for its existing `skin_temperature_c` channel. The synthetic input remains approximately 33.4 C; the returned quantized value is preserved without additional rounding. This is a provisional simulated skin-temperature use, not evidence of sensor placement, core-temperature measurement, or verified MAX30205 hardware compatibility. Raw register bytes and comparator pin states remain available in the standalone simulator and are not physiological measurements or backend alerts. The existing five-metric `demo.v1` contract, sensor identity, and historical profiles remain unchanged. Missing events do not sample the temperature simulator and store nulls.
