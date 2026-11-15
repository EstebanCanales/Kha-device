# Módulo de inteligencia artificial

## Objetivo

Construir un módulo Python dentro del monolito que analice información médica y datos espaciales mediante dos modelos especializados. Un tercer modelo combinará ambos análisis y generará un resumen.

## Estado

- **Implementado y probado:** contratos, entradas desde el análisis del backend, motor determinista `rules`, orquestación de las tres etapas, interfaz interna (`ia.run_pipeline`), el endpoint `POST /api/v1/sessions/{uuid}/summary/` y pruebas unitarias con modelos simulados.
- **Motor `ollama`:** los tres modelos servidos por un Ollama local. `ia/ollama/setup.sh` los prepara desde Hugging Face. Ver "Uso con Ollama".
- **Motor `huggingface`:** los mismos modelos con transformers y PEFT (carga diferida y secuencial). Sin probar con los pesos reales.
- **Pendiente:** evaluación de calidad, idioma y alucinaciones; mediciones de memoria y latencia; revisión médica; ejecutar fuera de la petición HTTP.

## Uso

```bash
uv run python manage.py test ia                  # pruebas con motores simulados
IA_ENGINE=rules uv run python manage.py runserver # predeterminado: sin modelos
```

### Uso con Ollama

Con `ollama serve` corriendo:

```bash
ia/ollama/setup.sh                                # una vez: ~6,4 GB de descarga y ~12 GB de disco
IA_ENGINE=ollama uv run python manage.py runserver
```

El script crea tres modelos locales: `kha-health` (el modelo médico de Hugging Face importado y cuantizado a q4_K_M), `kha-astronomy` (`llama3.2:3b` más el adaptador LoRA de astronomía de Hugging Face) y `granite3.3:2b` (IBM Granite 3.3 2B desde el registro de Ollama, el mismo modelo que `ibm-granite/granite-3.3-2b-instruct`). Los pesos descargados quedan en `ia/ollama/models/`, fuera de git. Cada nombre se cambia con `IA_OLLAMA_MODEL_HEALTH`, `IA_OLLAMA_MODEL_SPACE` e `IA_OLLAMA_MODEL_SYNTHESIS` (por ejemplo, `llama3.2:3b` para una prueba rápida). `OLLAMA_HOST`, `IA_OLLAMA_KEEP_ALIVE` e `IA_TIMEOUT` ajustan la conexión.

La petición `POST /api/v1/sessions/{uuid}/summary/` espera a que respondan los tres modelos en secuencia. El primer uso carga cada modelo en memoria y es el más lento.

### Qué se observó al ejecutarlos

Ejecutados con Ollama sobre datos simulados (tres llamadas, unos 15 s con modelos ya cargados en un Mac de 18 GB):

- **Funciona de punta a punta:** los tres modelos responden, el JSON se interpreta y la pantalla muestra el resultado.
- **Los modelos pequeños se equivocan.** Sin instrucciones estrictas, `llama3.2:3b` interpretó los cambios como "una respuesta del cuerpo a un estrés": justo lo que no debe hacer. Los prompts actuales le piden solo repetir qué cambió y cuánto, y no mencionar causas, riesgo ni tratamiento. El adaptador de astronomía y Granite escribieron cosas como "aumentó de 0.260045 mGy a 0.260045 mGy".
- **El modelo médico (`kha-health`) corrompe las tildes en español.** Con la importación a q4_K_M escribió «cardñaca» y «oxùgeno»; `llama3.2:3b` sin ajuste médico las escribe bien. Es un ajuste fino hecho sobre datos médicos, probablemente en inglés. Si importa el español, apunta `IA_OLLAMA_MODEL_HEALTH` a otro modelo (por ejemplo `llama3.2:3b`) o evalúa el modelo médico con prompts en inglés.
- **El adaptador de astronomía está afinado para preguntas de opción múltiple (MMLU), no para describir lecturas.** Cumple el formato, pero su utilidad aquí es limitada.
- **Los modelos tradujeron las claves del JSON** ("análisis" en vez de "analysis"). Se aceptan ambas formas.

Por eso el diseño no confía en el texto del modelo: los hallazgos, los cambios marcados y los datos faltantes salen siempre de las lecturas (`monitoring/analysis.py`), y lo que escribe un modelo se muestra aparte, rotulado como "puede contener errores". Además se advierte cuando el modelo cita cifras que no están en las lecturas o describe un cambio entre dos cifras idénticas, y si un modelo devuelve texto vacío se muestran las frases calculadas. Nada de esto reemplaza la revisión médica.

### Comparar modelos: `ia.evaluation`

```bash
uv run python -m ia.evaluation -v                                   # combinaciones por defecto
uv run python -m ia.evaluation --config mia=llama3.2:3b,llama3.2:3b,granite3.3:2b
```

Ejecuta cada combinación (salud, espacio, síntesis) sobre tres casos sintéticos (cambios fuertes, todo estable, pocos datos) y puntúa **lo que escribió el modelo**, no lo que la app terminó mostrando: JSON válido, sin interpretación médica, sin cifras que no están en las lecturas, sin «cambio» entre dos cifras iguales, tildes limpias y mención de cada cambio. No juzga si algo es médicamente correcto; eso lo hace una persona.

Resultado del 15 de noviembre de 2026 (Mac con 18 GB, temperatura 0, 3 casos × 3 modelos = 54 comprobaciones por fila):

| combinación | fallos | s/llamada | qué falló |
| --- | --- | --- | --- |
| `kha-health` + `kha-astronomy` + `granite3.3:2b` (los de este README) | 6 | 4,8 | tildes rotas (3), cambios falsos (2), cifra inventada (1) |
| `llama3.2:3b` en los tres | 3 | 2,8 | cambio entre cifras iguales (2), cifra inventada (1) |
| `llama3.2:3b` + `granite3.3:2b` en la síntesis | 5 | 2,9 | cambios falsos (3), cifra inventada (1), interpretación (1) |
| `gemma3:4b` en los tres | 4 | 3,2 | cifras inventadas (4), con datos escasos |
| `gemma3:12b` en los tres | 2 | 11,8 | cifra inventada (1), interpretación (1) |

Con tres casos y modelos deterministas, esto orienta pero no es una evaluación estadística. Lo que sí muestra es que los modelos del README no son los mejores para esta tarea concreta (describir lecturas ya calculadas), y que los pequeños inventan cifras sobre todo cuando hay pocos datos: por eso el motor **descarta** el texto de un modelo que cita cifras ausentes de las lecturas y muestra las frases calculadas. Cambiar de modelo no requiere código: `IA_OLLAMA_MODEL_HEALTH`, `IA_OLLAMA_MODEL_SPACE` e `IA_OLLAMA_MODEL_SYNTHESIS`.

### Uso con transformers

Para los modelos reales con transformers:

```bash
uv sync --extra ia
export HF_TOKEN=...            # y aceptar los términos de Llama en Hugging Face
IA_ENGINE=huggingface uv run python manage.py runserver
```

Variables: `IA_ENGINE`, `IA_DEVICE` (`auto` por defecto), `IA_KEEP_LOADED` (`false` carga un modelo cada vez y lo libera), `IA_MAX_NEW_TOKENS`, y `IA_MODEL_HEALTH`, `IA_MODEL_ASTRONOMY_BASE`, `IA_MODEL_ASTRONOMY_ADAPTER`, `IA_MODEL_SYNTHESIS` para cambiar los repositorios.

Cada especialista recibe frases calculadas por `monitoring/analysis.py` (seudonimizadas, sin nombres ni texto libre, máximo 40 frases de 300 caracteres) y devuelve análisis y limitaciones. Cada informe incluye además una frase calculada (`headline`) con el recuento de cambios; la síntesis la usa para no repetir los detalles de cada especialista. Granite recibe ambos informes y devuelve hallazgos, incertidumbres y datos faltantes. Los cambios marcados por el análisis y los datos faltantes calculados se conservan aunque el modelo no devuelva JSON válido.

## Modelos de Hugging Face

| Función | Modelo | Uso previsto |
| --- | --- | --- |
| Salud | [MohamedAhmedAE/Llama-3.2-3B-Instruct-Medical-Finetuned-merged](https://huggingface.co/MohamedAhmedAE/Llama-3.2-3B-Instruct-Medical-Finetuned-merged) | Analizar información médica en texto. |
| Astronomía | [ojayy/llama32-3b-mmlu-astronomy-lora](https://huggingface.co/ojayy/llama32-3b-mmlu-astronomy-lora) | Analizar información astronómica en texto. Es un adaptador LoRA que requiere el modelo base [meta-llama/Llama-3.2-3B-Instruct](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) y PEFT. |
| Síntesis | [ibm-granite/granite-3.3-2b-instruct](https://huggingface.co/ibm-granite/granite-3.3-2b-instruct) | Integrar los resultados de ambos especialistas y producir un resumen. |

Los tres son modelos de generación de texto: el formato y la transformación de datos médicos y espaciales a texto estructurado quedan por definir. El modelo astronómico está orientado a astronomía; su utilidad para otros datos espaciales debe evaluarse. Las salidas médicas requieren validación profesional y no deben tratarse como diagnósticos.

## Flujo propuesto

1. El monolito entrega al módulo los datos médicos y espaciales, junto con el contexto necesario.
2. Cada especialista procesa su entrada y devuelve un análisis con sus limitaciones.
3. Granite recibe ambos análisis y produce un resumen que distinga hallazgos, incertidumbres y datos faltantes.
4. El módulo devuelve el resultado al monolito mediante una interfaz interna; no se plantea un servicio independiente por ahora.

## Entorno previsto

- Python y [uv](https://docs.astral.sh/uv/) para gestionar proyecto, entorno y dependencias.
- Hugging Face Transformers y PyTorch para inferencia; PEFT para cargar el adaptador de astronomía. Evaluar Accelerate para asignación de dispositivos.
- Acceso a Hugging Face y aceptación de los términos de Llama cuando corresponda. Configurar credenciales mediante variables de entorno, sin guardarlas en el repositorio.
- Determinar memoria, almacenamiento y hardware mediante pruebas; los requisitos dependen de la precisión, cuantización y carga simultánea. Considerar carga diferida o secuencial si no caben los modelos juntos.

## TODO

- [x] Definir qué datos médicos y espaciales recibirá el módulo, sus formatos y el resultado esperado.
- [x] Inicializar el proyecto en `ia/` con uv, definir versión de Python y registrar dependencias y archivo de bloqueo.
- [ ] Configurar acceso a Hugging Face, revisar licencias y aceptar los términos de los modelos cuando corresponda (`HF_TOKEN` por variable de entorno; la aceptación de Llama la hace cada persona).
- [x] Implementar carga y configuración del modelo médico (sin probar con pesos reales).
- [x] Implementar carga del modelo base Llama y del adaptador LoRA de astronomía con PEFT.
- [x] Implementar carga y configuración del modelo Granite (sin probar con pesos reales). para síntesis.
- [x] Definir contratos de entrada y salida, límites de longitud y tratamiento de errores para cada modelo.
- [x] Implementar la orquestación de ambos análisis y su síntesis, con una interfaz interna para el monolito.
- [x] Diseñar el manejo de datos médicos: minimizar datos sensibles, controlar acceso y evitar registros con información personal.
- [ ] Evaluar calidad, idioma, alucinaciones y límites de los modelos con ejemplos representativos; incluir revisión médica cuando corresponda.
- [ ] Medir memoria, almacenamiento, latencia y opciones de cuantización en el hardware objetivo.
- [x] Añadir pruebas unitarias con modelos simulados y pruebas de integración opcionales con modelos reales.
- [ ] Documentar instalación, configuración y ejecución reales con los pesos descargados (la sección Uso cubre el motor `rules`; el motor `huggingface` queda por validar).
