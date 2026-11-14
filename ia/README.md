# Módulo de inteligencia artificial

## Objetivo

Construir un módulo Python dentro del monolito que analice información médica y datos espaciales mediante dos modelos especializados. Un tercer modelo combinará ambos análisis y generará un resumen. Este documento describe el proyecto propuesto: **los modelos y la integración todavía no están implementados**.

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

- [ ] Definir qué datos médicos y espaciales recibirá el módulo, sus formatos y el resultado esperado.
- [ ] Inicializar el proyecto en `ia/` con uv, definir versión de Python y registrar dependencias y archivo de bloqueo.
- [ ] Configurar acceso a Hugging Face, revisar licencias y aceptar los términos de los modelos cuando corresponda.
- [ ] Implementar carga y configuración del modelo médico.
- [ ] Implementar carga del modelo base Llama y del adaptador LoRA de astronomía con PEFT.
- [ ] Implementar carga y configuración del modelo Granite para síntesis.
- [ ] Definir contratos de entrada y salida, límites de longitud y tratamiento de errores para cada modelo.
- [ ] Implementar la orquestación de ambos análisis y su síntesis, con una interfaz interna para el monolito.
- [ ] Diseñar el manejo de datos médicos: minimizar datos sensibles, controlar acceso y evitar registros con información personal.
- [ ] Evaluar calidad, idioma, alucinaciones y límites de los modelos con ejemplos representativos; incluir revisión médica cuando corresponda.
- [ ] Medir memoria, almacenamiento, latencia y opciones de cuantización en el hardware objetivo.
- [ ] Añadir pruebas unitarias con modelos simulados y pruebas de integración opcionales con modelos reales.
- [ ] Documentar instalación, configuración y ejecución reales una vez implementadas.
