AGENTS.md — Backend de monitoreo de astronautas
1. Propósito y contexto
Actúa como agente de desarrollo del backend de este proyecto. La tecnología principal es Django y este archivo está dirigido a Codex.

El sistema recibirá telemetría de un arnés de monitoreo fisiológico y un dosímetro activo de radiación ionizante que llevará un astronauta. Los dominios requeridos son:
- Sistema cardiovascular.
- Sistema respiratorio.
- Oxigenación sanguínea.
- Temperatura.
- Actividad física y contexto de gravedad alterada.
- Radiación: tasa de dosis, dosis absorbida acumulada, historial individual y tiempo de exposición registrado.
La etapa actual consiste en preparar un backend funcional para integrar sensores. No se han confirmado modelos de hardware, firmware, frecuencias de muestreo, interfaces de comunicación ni formatos reales de sus mensajes.

Trata esta etapa como un prototipo de adquisición y consulta de datos. No atribuyas al sistema validación clínica, certificación aeroespacial ni capacidad de diagnóstico.
2. Misión actual de Codex
2.1. Resultado esperado
Implementa un flujo verificable de extremo a extremo: un simulador autenticado envía lecturas, el backend las valida y guarda, y un usuario autorizado consulta su historial.

Prioridades, en este orden:
1. Inspeccionar el repositorio y aprovechar su estructura existente.
2. Configurar Django, dependencias, variables de entorno y base de datos.
3. Modelar participantes, sesiones, dispositivos, sensores y lecturas.
4. Definir e implementar un contrato versionado de ingesta.
5. Proteger la recepción y consulta con autenticación y autorización.
6. Soportar reenvíos, datos retrasados y desconexiones sin duplicar mediciones.
7. Incorporar simulación, pruebas relevantes y documentación reproducible.
2.2. Fuera de esta primera etapa
No implementar frontend, firmware, diagnóstico, alertas médicas, inteligencia artificial, recomendaciones de tratamiento ni cálculos de riesgo radiológico. No añadir streaming, procesamiento de ECG, MQTT, colas o infraestructura distribuida sin un requisito concreto.

El backend debe poder ampliarse después, pero no necesita implementar por anticipado todas esas funciones.
3. Forma de trabajar
3.1. Inspección y autonomía
- Lee el README, las instrucciones aplicables, los archivos de dependencias, la configuración, las migraciones y las pruebas antes de editar.
- Revisa el estado de Git y conserva los cambios del usuario. No sobrescribas trabajo ajeno ni hagas operaciones destructivas.
- Si ya existe una implementación, adáptala. Si el repositorio está vacío, crea la base descrita aquí.
- Ejecuta las tareas reversibles necesarias para completar la misión; no te quedes únicamente en un plan.
- Registra las decisiones técnicas provisionales y continúa con simulación cuando falte hardware. Pregunta solo si una decisión bloqueante no puede aislarse mediante un supuesto documentado.
- No inventes fichas técnicas, puertos, credenciales, unidades de salida, comandos existentes ni resultados de pruebas.
- No despliegues, publiques, hagas push ni modifiques servicios externos salvo solicitud explícita. Sigue la política de commits del repositorio; si no existe, deja los cambios preparados para revisión.
3.2. Comunicación y código
- Explica avances y resultados en español, de manera directa. Usa inglés para nombres de código, rutas y claves JSON.
- Prefiere funciones pequeñas, nombres descriptivos y comentarios que expliquen decisiones.
- Sigue las convenciones del repositorio. Evita refactorizaciones ajenas a la tarea y dependencias sin necesidad demostrable.
- Mantén este archivo como instrucciones operativas. Coloca especificaciones extensas y decisiones detalladas en docs/.
4. Base técnica y organización
4.1. Decisiones iniciales
Cuando el repositorio todavía no tenga decisiones equivalentes, utiliza:
Componente	Base propuesta
Backend	Python y Django, con versiones compatibles y mantenidas
API	Django REST Framework
Base de datos	PostgreSQL
Transporte inicial	HTTP con JSON; HTTPS fuera del desarrollo local
Administración	Django Admin para participantes, sesiones y dispositivos
Contrato	API /api/v1/ y esquema OpenAPI
Pruebas	Runner existente; por defecto, pruebas de Django y DRF
Calidad	Herramientas existentes; Ruff si el proyecto nuevo necesita un linter


Estas son decisiones iniciales de software, no características confirmadas del hardware. Respeta las herramientas ya adoptadas y documenta cualquier cambio necesario. Fija dependencias de forma reproducible y no actualices versiones mayores por conveniencia.
4.2. Separación de responsabilidades
Mantén un monolito modular. Si partes desde cero, organiza las responsabilidades en config/, participants/, devices/ y telemetry/; pueden agruparse si el tamaño inicial lo justifica.
- Modelos: datos, relaciones, índices y restricciones de integridad.
- Serializers: forma del contrato y validación de entradas.
- Servicios de ingesta: autorización contextual, idempotencia y persistencia transaccional.
- Vistas: coordinación HTTP y respuestas; evita lógica de dominio extensa.
- Consultas: filtros, permisos, paginación y orden estable.
- Simulador: cliente del mismo endpoint que utilizará la integración real.
La lógica de ingesta no debe depender del transporte físico. Un adaptador futuro podrá traducir mensajes de un gateway al mismo contrato sin duplicar las reglas del dominio.
5. Datos que debe contemplar el sistema
5.1. Catálogo inicial de métricas
Las métricas siguientes son propuestas de modelado. Habilita cada una en un dispositivo real únicamente cuando su sensor y contrato estén confirmados. No presentes una señal como disponible solo porque el backend admite almacenarla.
Dominio	Métricas o datos previstos	Unidad o criterio
Cardiovascular	Frecuencia cardíaca: heart_rate	bpm
Respiratorio	Frecuencia respiratoria: respiratory_rate	breaths/min
Oxigenación	Saturación periférica estimada: spo2	%; no confundir con concentración de oxígeno ambiental
Temperatura	skin_temperature, core_temperature o ambient_temperature, según procedencia	degC; conservar sitio y método
Actividad	Aceleración por eje y, si existe giroscopio, velocidad angular	m/s2 y rad/s; indicar ejes y marco de referencia
Gravedad alterada	Contexto de sesión: terrestre, microgravedad, gravedad parcial, hipergravedad o desconocido	Metadatos declarados, con procedencia
Radiación	Tasa de dosis	Magnitud y unidad exactas que reporte el dosímetro
Radiación	Dosis absorbida acumulada, si realmente se mide	Gy o submúltiplos identificados
Radiación	Tiempo de exposición registrado	s, con criterio de inicio, pausa y reinicio
Historial	Lecturas y períodos de exposición por participante y sesión	Ordenados por tiempo de medición


5.2. Límites de interpretación
- No asumas ECG, presión arterial, temperatura central o volumen respiratorio si no hay hardware y procesamiento que los produzcan.
- Distingue una medición directa de una estimación. Guarda método y versión cuando un valor sea calculado.
- No clasifiques automáticamente el régimen de gravedad a partir de una lectura aislada del acelerómetro. Conserva los datos inerciales y el contexto declarado por separado.
- No conviertas ausencia de datos, sensor desconectado o mala señal en un valor cero.
5.3. Reglas específicas de dosimetría
- Guarda la magnitud dosimétrica, no solo un campo genérico llamado radiation. Distingue dosis absorbida, dosis equivalente y magnitudes operacionales como equivalente de dosis personal Hp(d) cuando corresponda al instrumento.
- La dosis absorbida se expresa en gray (Gy); otras magnitudes, como dosis equivalente y equivalente de dosis personal, usan sievert (Sv). No intercambies ambas unidades ni deduzcas una a partir de la otra sin un modelo validado y la información requerida.
- Si el sensor reporta µSv/h, no lo etiquetes como tasa de dosis absorbida. Si reporta conteos, no los transformes en dosis sin calibración documentada.
- Conserva la unidad original y permite normalizar únicamente conversiones explícitas dentro de una misma magnitud. Documenta los códigos de unidades aceptados, incluidos prefijos como uGy o uSv.
- Registra si la dosis es un contador acumulado del dispositivo o un incremento de un intervalo. No sumes entre sí las sucesivas lecturas de un contador acumulativo.
- Identifica la época del contador y los reinicios. Un reinicio del dispositivo o una nueva asignación a un participante no puede mezclarse silenciosamente con el historial anterior.
- En esta etapa, guarda y consulta las lecturas originales. No integres tasas para producir dosis ni fabriques totales personales a partir de contadores cuya referencia sea desconocida.
- Conserva el tiempo registrado por el instrumento o el protocolo de exposición. No lo sustituyas por el tiempo transcurrido desde la primera petición HTTP.
- Los vacíos de transmisión deben permanecer identificables; no significan ausencia de exposición.
6. Modelo de dominio y trazabilidad
Implementa las entidades mínimas equivalentes a las siguientes; adapta los nombres a las convenciones existentes:
Entidad	Responsabilidad
Participant	Identificador seudónimo del astronauta o participante; sin datos personales innecesarios
MonitoringSession	Participante, inicio, cierre y contexto del monitoreo
Device	Arnés, dosímetro o gateway registrado; estado, identificador y versión de firmware cuando se conozca
Sensor	Canal o sensor de un dispositivo, métricas admitidas y perfil de configuración/calibración
SessionDevice	Asociación temporal autorizada entre sesión y dispositivo
TelemetryPacket	Identificador del evento, versión de esquema, dispositivo, sesión, tiempo y procedencia
Measurement	Sensor, métrica, valor, unidad, calidad y referencia al paquete


Reglas de modelado:
- Usa identificadores estables, claves foráneas y restricciones en base de datos; no dependas solo del serializer.
- Resuelve el participante mediante una sesión autorizada. No aceptes un participant_id arbitrario enviado por el dispositivo como prueba de identidad.
- Comprueba que el sensor pertenece al dispositivo y que este estaba asignado a la sesión en el momento de la medición.
- Conserva la asociación histórica aunque el dispositivo se reasigne. No vincules datos antiguos usando exclusivamente su propietario actual.
- Guarda observed_at como tiempo de medición y received_at como tiempo generado por el servidor. Usa fechas con zona horaria y normaliza a UTC.
- Conserva la versión del perfil de sensor/calibración usada, o marca que es desconocida; no alteres el significado histórico al editar una configuración.
- Distingue datos simulated y hardware. La procedencia debe coincidir con el perfil registrado del emisor; un payload no puede convertir un simulador en hardware real.
- Protege la precisión numérica de dosis y contadores. Elige tipos y resolución documentados; no redondees silenciosamente.
- Usa columnas consultables para identidad, métrica, tiempo y valor. Reserva JSON para metadatos acotados o el payload original autorizado, no como sustituto de todo el modelo.
- Indexa las consultas por sesión, sensor/métrica y tiempo. Las lecturas aceptadas serán de solo lectura en API y Admin; no habilites edición o borrado genérico.
7. Contrato inicial de ingesta
7.1. Forma del mensaje
Define POST /api/v1/telemetry/batches/ con una lista acotada de paquetes. Cada paquete identifica el dispositivo, la sesión, el instante de medición y sus lecturas.

Ejemplo exclusivamente sintético; no especifica valores clínicos de referencia ni capacidades del hardware:
{
  "schema_version": 1,
  "packets": [
    {
      "packet_id": "27980ce0-91a0-4b41-9ed8-89f0a34cc4c4",
      "device_id": "harness-sim-001",
      "session_id": "session-demo-001",
      "observed_at": "2026-11-14T16:00:00Z",
      "source": "simulated",
      "readings": [
        {
          "sensor_id": "hr-sim-001",
          "metric": "heart_rate",
          "value": "78.0",
          "unit": "bpm",
          "quality": "valid"
        }
      ]
    }
  ]
}
Documenta el tipo y formato de cada identificador; los identificadores legibles del ejemplo deben existir en los datos de demostración. En este contrato, los valores escalares se transmiten como cadenas decimales finitas para conservar precisión. Define explícitamente cómo representar vectores y lecturas ausentes.

Todas las lecturas de un paquete comparten observed_at. Si se capturaron en instantes distintos, envíalas en paquetes distintos. No supongas sincronización entre sensores por haber llegado en el mismo lote.
7.2. Validación y calidad
- Valida esquema, campos obligatorios, tipos, tamaño, versión, identificadores, permisos y pertenencia del sensor.
- Acepta solo métricas y unidades habilitadas en el perfil del sensor. Rechaza versiones o campos desconocidos fuera de una extensión de metadatos documentada.
- Rechaza NaN, infinito y datos estructuralmente inválidos. Define límites técnicos de longitud, precisión y cantidad.
- Separa los límites matemáticos o instrumentales de los umbrales médicos. No rechaces una lectura solo por estar fuera de un supuesto rango saludable.
- Define estados de calidad, por ejemplo valid, unreliable y missing. Permite null únicamente para una ausencia explícita y documentada; un valor ausente no es cero.
- Acepta datos fuera de orden dentro de una política documentada. Las tolerancias de reloj y antigüedad serán configurables y no inventarán tiempos de medición.
- Un paquete sin tiempo confiable requiere una política explícita; nunca sustituyas silenciosamente observed_at por received_at.
7.3. Idempotencia, transacciones y reintentos
- El emisor genera un packet_id estable antes del primer envío y lo conserva en los reintentos.
- Impón unicidad en base de datos sobre (device_id, packet_id) y controla duplicados también dentro del mismo lote.
- Un reenvío idéntico devuelve confirmación de duplicado, sin insertar nuevas lecturas. Reutilizar la misma identidad con contenido diferente devuelve conflicto.
- Compara contenido mediante una representación canónica documentada; excluye campos generados por el servidor. Incluye sesión, tiempo, lecturas, unidades y procedencia.
- Implementa la protección bajo concurrencia; una consulta previa de existencia no es suficiente.
- Para el MVP, cada lote es atómico: si un paquete es inválido o conflictivo, no se inserta ninguno de los paquetes nuevos. Los duplicados idénticos no son un error.
- Usa transacciones breves. No confirmes éxito antes de que los datos se hayan persistido.
- Devuelve estado por paquete y totales de insertados/duplicados. Documenta 400, errores de autenticación/autorización, 409, 413, 429 y fallos temporales según la implementación.
- El simulador debe poder reenviar el mismo lote y reproducir retrasos. Documenta reintentos con espera creciente para fallos temporales, sin crear identidades nuevas.
8. API de consulta y operación
8.1. Endpoints mínimos
Endpoint propuesto	Función
POST /api/v1/telemetry/batches/	Ingesta autenticada por dispositivo o gateway autorizado
GET /api/v1/sessions/	Sesiones visibles para el usuario
GET /api/v1/sessions/{id}/measurements/	Historial paginado con filtros por métrica, sensor y fechas
GET /api/v1/sessions/{id}/latest/	Última lectura por sensor y métrica, según observed_at
GET /healthz/	Estado básico del proceso, sin información sensible
GET /readyz/	Disponibilidad de las dependencias mínimas, con respuesta limitada


El historial individual puede consultarse mediante las sesiones autorizadas del participante, incluyendo el filtro correspondiente. No necesitas un servicio separado para reconstruirlo.
8.2. Reglas de consulta
- Aplica autorización tanto a detalles como a listados y filtros. Estar autenticado no concede acceso a todos los participantes.
- Pagina, limita rangos de consulta y usa orden estable por tiempo e identificador.
- Devuelve unidad, calidad, procedencia y tiempos junto con el valor.
- La lectura más reciente no es necesariamente una lectura actual: muestra su tiempo y no la declares vigente por haber sido recibida recientemente.
- Separa por sensor y magnitud; no mezcles temperatura cutánea con central ni contadores dosimétricos con referencias diferentes.
- Filtra por defecto datos reales y simulados de forma explícita; no los combines silenciosamente en respuestas o agregaciones.
9. Seguridad y configuración
9.1. Identidad y acceso
- Distingue credenciales de dispositivos de cuentas humanas. Los emisores solo pueden enviar por los dispositivos y sesiones asignados.
- No utilices un token global compartido por todos los dispositivos. Las credenciales deben poder revocarse y rotarse individualmente.
- Usa mecanismos mantenidos y almacena credenciales de forma segura; no diseñes criptografía propia ni guardes secretos de emisor recuperables si basta un verificador.
- Implementa permisos mínimos: administración de configuración, consulta autorizada e ingesta. Una credencial de ingesta no habilita lectura del historial.
- Conserva CSRF para sesiones de navegador. No desactives protecciones globales para resolver problemas de autenticación.
9.2. Configuración y datos sensibles
- Usa variables de entorno para secretos y configuración. Entrega .env.example sin valores reales y excluye .env del control de versiones.
- Separa configuración local y de despliegue. En un despliegue, exige DEBUG=False, hosts permitidos y HTTPS configurado correctamente.
- Limita el tamaño de cuerpos, paquetes por lote, lecturas por paquete y frecuencia de peticiones.
- No registres tokens, secretos, nombres ni payloads completos con datos fisiológicos en los logs. Registra identificadores técnicos, resultado, duración y conteos suficientes para depurar.
- Usa solo datos sintéticos en fixtures, pruebas y demostraciones.
- Documenta la retención como decisión pendiente; no implementes borrado automático de historiales sin una política acordada.
10. Simulación y pruebas
10.1. Simulador reproducible
Proporciona un comando o script documentado que cree o utilice participantes, sesiones y dispositivos de demostración, y envíe mensajes por HTTP con autenticación.

Debe permitir controlar semilla, cantidad e intervalo de envío, y generar ejemplos de los dominios del proyecto mediante perfiles de sensor expresamente simulados. Incluye escenarios de duplicados, retrasos, falta de señal y reinicio de contador dosimétrico.

No presentes los perfiles simulados como compatibilidad verificada con instrumentos reales.
10.2. Pruebas obligatorias de comportamiento
- Un lote válido se persiste y puede consultarse con los permisos correctos.
- Credenciales ausentes, inválidas o revocadas no permiten ingesta.
- Un dispositivo no puede enviar por otro ni atribuir datos a una sesión ajena.
- Un usuario no puede consultar datos ajenos cambiando IDs, filtros o rutas.
- Un lote inválido revierte todas sus inserciones nuevas.
- Reintentos idénticos, incluidos los concurrentes, no duplican paquetes ni lecturas.
- Una identidad reutilizada con contenido distinto produce conflicto.
- Unidades incompatibles, versiones desconocidas y valores no finitos fallan de forma controlada.
- Datos retrasados conservan su sesión y tiempo originales; no reemplazan indebidamente la última lectura.
- La ausencia de señal no se convierte en cero y la simulación permanece identificada.
- Contadores acumulados y reiniciados se almacenan sin sumas o mezclas implícitas.
Comprueba restricciones y concurrencia con PostgreSQL. Si solo puedes probar con otra base de datos o falta infraestructura, identifica esa limitación; no afirmes equivalencia ni verificaciones que no ejecutaste.
10.3. Comprobaciones del proyecto
Usa los comandos reales del repositorio. En un proyecto Django nuevo, documenta y ejecuta, cuando el entorno lo permita:
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
Aplica migraciones únicamente sobre la base local o de pruebas destinada a esta tarea. Ejecuta también el linter configurado y valida la coherencia del esquema OpenAPI y sus ejemplos. No cambies las pruebas para esconder fallos del comportamiento requerido.
11. Documentación y definición de terminado
11.1. Entregables de esta misión
- Proyecto Django arrancable, dependencias reproducibles y configuración de ejemplo.
- Modelos, migraciones, índices y restricciones de integridad.
- Ingesta y consultas mínimas, con autenticación y permisos.
- Django Admin para configuración; telemetría de solo lectura.
- Esquema OpenAPI y ejemplos consistentes de peticiones y respuestas.
- Simulador y pruebas del flujo completo.
- README.md con instalación, configuración, migraciones, ejecución y pruebas.
- docs/telemetry-contract.md con métricas, unidades, tiempos, calidad, idempotencia y errores.
- docs/decisions.md con supuestos, decisiones provisionales y pendientes de hardware.
11.2. Criterio de aceptación
La misión está terminada cuando, siguiendo únicamente el README y con las dependencias disponibles, se puede levantar el backend, registrar una sesión de demostración, enviar un lote autenticado, consultarlo, reenviarlo sin duplicación y comprobar el rechazo de un emisor no autorizado.

La demostración debe usar el endpoint HTTP real, no insertar lecturas directamente en la base de datos para aparentar integración.

Al terminar, informa brevemente qué implementaste, cómo ejecutarlo, qué comprobaste, qué falló o no pudiste comprobar y qué sigue pendiente. No declares integración con hardware si solo se ha validado el simulador.
12. Información pendiente para conectar hardware real
Avanza con la infraestructura y la simulación mientras estos datos no estén disponibles:
1. Marca, modelo, ficha técnica y ubicación corporal de cada sensor.
2. Métricas y magnitudes reales del dosímetro, calibración, unidades y referencia de sus contadores.
3. Ejemplos reales de payload, protocolo de transporte y existencia de un gateway.
4. Frecuencias de muestreo, volumen esperado y si se enviarán resúmenes o formas de onda.
5. Sincronización de reloj, almacenamiento durante desconexiones y política de reenvíos.
6. Procedimiento de asignación de dispositivos, sesiones y reinicio de contadores.
7. Contexto de gravedad y fuente que lo determina.
8. Entorno de despliegue, usuarios autorizados, retención y necesidades futuras de alertas validadas.
No conviertas estas incógnitas en características confirmadas. Cuando llegue la especificación real, adapta y prueba el perfil o adaptador correspondiente y actualiza el contrato.
13. Referencias para implementación y aprendizaje
- Codex: instrucciones con AGENTS.md.
- Django: transacciones. Consulta la versión de documentación correspondiente al proyecto.
- Django REST Framework: permisos.
- IAEA: preguntas sobre protección radiológica; magnitudes de dosis, pregunta 23.
Estas referencias respaldan aspectos técnicos del contrato. No definen requisitos clínicos ni certifican el sistema para uso espacial.