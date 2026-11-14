# Modelo provisional de telemetría

`monitoring.models` define datos que el backend puede representar, no capacidades
confirmadas del arnés ni del dosímetro. Ningún `SensorCapability` se crea o habilita
automáticamente. La ingesta debe comprobar capacidad, asignación temporal,
procedencia y validez de cada valor dentro de una transacción antes de guardar.

- Los identificadores de participante, sesión, dispositivo y sensor son cadenas
  estables. `packet_id` y la época del contador usan UUID.
- Todas las fechas deben tener zona horaria. `observed_at` procede del emisor;
  `received_at` lo asigna el servidor. Un lote tardío conserva su tiempo original.
- Los escalares usan `Decimal(30,12)`: hasta 18 cifras enteras y 12 decimales.
  La API futura debe rechazar valores que no quepan; no redondearlos.
- Aceleración se representa por ejes X/Y/Z en `m/s2`, con marco de referencia
  declarado en el sensor. Actividad e inactividad son resultados derivados,
  pendientes de método y versión; no se infieren en este modelo.
- ECG tiene una tabla opcional de muestras crudas con índice, canal, instante,
  amplitud y unidad. Su formato de captura, frecuencia, derivaciones y método
  siguen pendientes; no hay adquisición ni procesamiento implementado. Requiere
  habilitar explícitamente la capacidad `ecg` del sensor.
- HRV, patrones de ritmo y respiración, y tendencias térmicas son resultados
  de `AnalysisResult`. Requieren un método y versión reales antes de guardarse;
  `input_source` conserva si procedían de datos simulados o de hardware.
- Las magnitudes dosimétricas en Gy y Sv permanecen separadas. Los contadores
  acumulados requieren `CounterEpoch` ligado a la asignación histórica. El
  historial individual se reconstruye desde las sesiones del participante;
  no se calculan totales ni riesgo.
- Las asignaciones de un dispositivo y las épocas de un contador no deben
  solaparse. La validación de intervalos cerrados está en `clean()`; índices
  únicos parciales impiden varias asignaciones o épocas abiertas en paralelo.
- `Measurement.quality=missing` exige `value=NULL`; `valid` y `unreliable`
  exigen un valor. La comprobación de unidades compatibles y pertenencia entre
  relaciones está en `clean()`, por lo que la API y Admin deben llamar a
  `full_clean()` o validar equivalentes antes de guardar. Las restricciones
  simples de calidad, unicidad y períodos están también en la base de datos.

Pendiente para hardware real: perfiles, unidad y magnitud exacta del dosímetro,
referencia y reinicio de sus contadores, formato ECG, procedencia de contexto de
gravedad, frecuencia de muestreo, reloj y política de retención.
