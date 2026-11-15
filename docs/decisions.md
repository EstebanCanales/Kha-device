# Decisiones provisionales

- El backend es un monolito Django/DRF. SQLite permite demostración local; PostgreSQL se configura con `DATABASE_URL` o con `DB_ENGINE=postgresql`. Las migraciones y toda la batería de pruebas se ejecutaron contra PostgreSQL 14 el 15 de noviembre de 2026 (ver más abajo).
- La configuración usa CRUD para participantes, sesiones, dispositivos, sensores, capacidades, asignaciones y épocas de contador. La ingesta crea paquetes y mediciones; el historial es de solo lectura. ECG crudo y resultados derivados continúan como modelos sin API de adquisición o análisis.
- Las claves primarias de `monitoring` son UUID v4. Los identificadores legibles se mantienen para contratos de dispositivo. Los usuarios de Django conservan las claves propias del framework.
- Cada dispositivo tiene credenciales revocables y verificadores con el hasher de Django. No se almacena el secreto recuperable. La rotación puede emitir una nueva credencial y revocar las anteriores.
- La lista de métricas representa posibilidades de almacenamiento. Solo `seed_demo` habilita perfiles **simulados**. No hay compatibilidad comprobada con hardware.
- No se calculan diagnósticos, alertas, riesgo radiológico, totales personales ni actividad a partir de aceleración. La retención y el borrado automático quedan pendientes.
- Se acepta telemetría atrasada dentro de la asignación temporal sin límite adicional de antigüedad. El futuro se limita por tolerancia configurable. La sincronización de relojes y política de datos sin tiempo confiable requieren especificación de hardware.
- La limitación de peticiones usa caché local y sirve para un proceso de desarrollo. Un despliegue con varios procesos necesita una caché compartida y pruebas de carga.
- El contrato v1 conserva magnitudes y unidades originales. La procedencia y la época de contador evitan mezclar datos de simulación o referencias de dosis distintas.

Pendiente antes de integrar equipos reales: modelos y fichas técnicas, magnitudes y calibración del dosímetro, payload y protocolo, frecuencia de muestreo, reloj y almacenamiento durante desconexiones, procedimiento de reasignación y reinicio, fuente del contexto de gravedad, retención, autorización operativa y entorno de despliegue.

## Ampliaciones del 14 de noviembre de 2026

Estas decisiones se tomaron a petición expresa del proyecto y amplían lo que `AGENTS.md` excluía sin un requisito concreto (interfaz, análisis y IA).

- **Perfiles de Kha-device 01.** `setup_kha_devices` registra el dosímetro CAD (`cad-sim-001`: cámaras DIS de alta y baja resolución, TMP117) y el dispositivo de signos vitales (`kha-vitals-sim-001`: MAX86178 y MAX30205). Siguen siendo **simulados**; los números de parte vienen de las notas del proyecto. La saturación aproximada de cada cámara (500–700 mGy y 5–7 Gy) se guarda como referencia de calibración sin verificar. Cada cámara es un contador acumulado con su propia época y sus valores no se suman. Se añadió la métrica `internal_temperature` (migración 0006) porque la temperatura del TMP117 es del circuito, no del cuerpo. El RV-3028 aporta la hora de cada medición y no genera una métrica.
- **Frecuencia respiratoria.** El simulador la envía como canal derivado (`method=ppg_modulation_simulated`). Estimarla de verdad exige la señal PPG o ECG cruda, que no se adquiere ni se procesa.
- **Análisis.** `monitoring/analysis.py` es estadística descriptiva calculada al consultar: no guarda resultados ni usa `AnalysisResult`. Compara las últimas lecturas con las primeras de la misma persona en la misma sesión (mediana y desviación absoluta mediana; cambio a partir de 3 desviaciones; ritmo de dosis a partir de 3 veces el inicial). Las constantes son provisionales: no son umbrales médicos ni radiológicos. No convierte unidades, no integra tasas y no calcula riesgo; trabaja con las diferencias de un mismo contador dentro de su época.
- **Ollama.** `IA_ENGINE=ollama` llama a la API HTTP de un Ollama local (`/api/chat`, `format=json`, temperatura 0), sin dependencias nuevas. Los modelos de Hugging Face se importan a Ollama con `ia/ollama/setup.sh`: el médico por importación de safetensors con cuantización q4_K_M y plantilla Llama 3 explícita, y el de astronomía como `ADAPTER` LoRA sobre `llama3.2:3b` del registro de Ollama (ese adaptador se entrenó sobre el modelo base completo, no sobre su versión cuantizada, así que su comportamiento puede diferir del de transformers). Granite viene del registro de Ollama. Los errores del motor tienen mensajes seguros y accionables que no incluyen texto de la petición.
- **Cifras inventadas: se descartan, no se avisan.** Si el texto de un especialista cita cifras que no están en las lecturas, o describe un cambio entre dos cifras idénticas, el motor lo descarta y muestra las frases calculadas, con el motivo. En la síntesis se eliminan solo esas frases. En una evaluación con ejemplos de pocos datos, `gemma3:4b` escribió «pasó de 60 a 70 lpm» y «15.3 microSievert», cifras sin ninguna base en las lecturas. Una advertencia al lado no basta para una cifra de dosis. Los modelos pueden dar redacción, no hechos.
- **Banco de modelos.** `python -m ia.evaluation` compara combinaciones sobre casos fijos con comprobaciones automáticas. Los modelos por defecto siguen siendo los del README del proyecto; la evaluación muestra que otros rinden mejor en esta tarea, y cambiarlos es una decisión del proyecto.
- **IA.** `ia/` es un paquete del monolito, no un servicio. El motor `rules` es determinista y es el predeterminado; el motor `huggingface` carga los tres modelos del README de forma diferida y secuencial (uno a la vez salvo `IA_KEEP_LOADED=true`). Los cambios marcados por el análisis y los datos faltantes calculados nunca dependen de lo que el modelo devuelva: se conservan aunque falle el JSON. Las entradas son agregados con seudónimo y los errores no repiten texto de la petición. Está sin probar con los pesos reales.
- **Datos espaciales.** Se asumió que la dosimetría y el contexto de gravedad son la entrada del especialista de astronomía. El modelo LoRA está afinado en astronomía general; su utilidad para dosimetría está por evaluar.
- **App.** El panel `/app/` lo sirve Django en el mismo origen, con sesión y CSRF de Django, sin CORS. Usa solo rutas `/api/v1/`. La landing enlaza a él con `PUBLIC_APP_URL`.
- **Un solo `overview`.** El panel pide análisis, series por sensor (últimas 24 horas desde el 15 de noviembre de 2026, antes 3; hasta 120 puntos, un contador por sensor y época) y el motor de IA activo en una única petición. Antes eran unas once, y si el servidor no respondía el navegador solo decía "Failed to fetch". Ahora los errores de red y de servidor se explican en la pantalla y se conservan los últimos datos.
- **Síntesis que resume.** Cada especialista aporta una frase calculada (`headline`: cuántas señales cambiaron) además de sus detalles. La síntesis del motor `rules` une esas frases y añade una nota de que los cambios coinciden en el tiempo sin implicar causa, solo si ambos especialistas detectaron cambios. Con modelos reales, esas frases calculadas siempre encabezan los hallazgos.
- **Resumen por `POST`.** Genera texto y no guarda nada; puede tardar minutos con modelos reales y corre dentro de la petición. Un despliegue real necesitará una cola o ejecución en segundo plano, hoy fuera de alcance.

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

## NASA DONKI radiation context

- Use the requested `https://api.nasa.gov/DONKI/RBE` endpoint and `RADATION_API_KEY` environment variable. No dependency or database migration is required.
- RBE records are external environmental events, not worn-dosimeter measurements. Preserve original event fields and retrieval provenance separately from hardware/simulated telemetry; do not derive Gy, Sv, rates, counters, or risk from events.
- Provide a bounded client, `scripts/nasa_radiation.py`, and an authorized session `radiation-context` read action. No credentials or participant data appear in outputs/upstream queries, respectively.
- Cache only successful results for 15 minutes; retain `fetched_at`. Explicitly report upstream failures instead of fabricating readings or silently falling back. Database persistence, spatial correlation, and incorporation into combined reports are outside this change.


## Decisiones del 15 de noviembre de 2026

Tomadas a petición del proyecto durante el alojamiento del prototipo.

- **PostgreSQL verificado.** La migración 0003 convertía claves enteras a UUID alterando la columna. SQLite lo acepta porque reconstruye la tabla; PostgreSQL responde `cannot cast type bigint to uuid`. En PostgreSQL la migración ahora borra y vuelve a crear las tablas, que el paso anterior ya exige vacías, a partir del estado nuevo; en SQLite se comporta igual que antes. Con ese cambio, las migraciones y las pruebas pasan en PostgreSQL 14.
- **`DATABASE_URL`.** Se añadió para bases PostgreSQL alojadas, sin dependencias nuevas (`config/database.py`). Solo se aceptan URL de PostgreSQL. Las conexiones se reutilizan 60 segundos y se comprueban antes de usarse.
- **Layerbase descartado.** La base de tipo "sqlite 3" de Layerbase expone SQLite tras el protocolo de PostgreSQL (`pgsqlite`). El backend de PostgreSQL de Django no pudo crear ni su tabla de migraciones. Adaptarlo exigía un backend propio y renunciar a las garantías verificadas con PostgreSQL, así que se usa el PostgreSQL de Railway.
- **Alojamiento en Railway.** Tres servicios: backend (gunicorn y WhiteNoise), PostgreSQL y landing estática. La base solo es accesible desde la red privada del proyecto. Detrás del proxy se confía en la cabecera `X-Forwarded-Proto`, y solo cuando Railway o `DJANGO_BEHIND_PROXY` lo indican. Los archivos estáticos se recopilan al arrancar porque el paso previo al despliegue corre en otro contenedor.
- **Ritmo de los datos simulados.** Un dato cada 30 minutos, con una ventana de 24 horas por defecto (48 muestras). Es una elección de simulación, no una frecuencia de hardware confirmada. La ventana de las gráficas pasó de 3 a 24 horas para que el análisis, que necesita 20 lecturas, tenga datos suficientes.
- **Registro de cuentas.** `/accounts/signup/` crea cuentas sin privilegios. Está apagado fuera de desarrollo salvo que se active. Una cuenta nueva no lee nada por defecto; `SIGNUP_DEMO_SESSION` le concede una sola sesión de demostración, también al iniciar sesión. Hay un límite de 10 intentos por dirección y hora. No hay verificación de correo ni recuperación de contraseña: quedan pendientes de elegir un servicio de correo.
- **Demostración sin usuario.** `demo_kha --no-user` carga la sesión sin crear cuenta, para que ninguna contraseña generada aparezca en los registros del despliegue.
- **Landing bilingüe, inglés principal.** El inglés se sirve en `/` y el español en `/es/`. El idioma no cambia según el navegador; solo según lo que la persona eligió en el selector.
- **Video.** Se publica una copia a 1080p del video de presentación. El original en 4K (91 MB) queda fuera del repositorio.
- **Nota de visión en la landing.** La sección "What makes us different" describe capacidades futuras (orientación, procedimientos de emergencia). Lleva una nota que aclara que el prototipo actual no diagnostica ni emite alertas médicas, para no afirmar lo que `AGENTS.md` excluye.
- **Panel sin sesión.** Una cuenta sin sesiones legibles ve una explicación y el panel no pide datos a la API.


## Open read access for the hosted demonstration (2026-11-15)

The project owner asked that every user be able to see everything in the hosted prototype. `OPEN_READ_ACCESS=true`
makes every signed-in account a reader of every session; it is set in the Railway deployment and off by default
everywhere else, where per-session authorization still applies. It only widens reading: sessions, devices and
configuration remain staff-only to change. The hosted database holds simulated data only. This setting must be
turned off before any session stores a real participant's readings.
