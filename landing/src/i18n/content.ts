// Todo el texto de la página, por idioma. Los componentes leen de aquí; ninguno escribe texto propio.
// Para añadir un idioma: copia `es`, tradúcelo y regístralo en `content` y en `LANGS`.

export type Lang = 'es' | 'en';
export const LANGS: Lang[] = ['en', 'es'];
// El inglés es el idioma principal: vive en la raíz; el español, bajo /es/.
export const DEFAULT_LANG: Lang = 'en';

type Pair = [string, string];

const es = {
	meta: {
		title: 'Kha-device 01',
		description: 'Datos médicos y datos espaciales, analizados juntos.',
	},
	langSwitch: { label: 'Idioma', es: 'Español', en: 'English' },
	hero: {
		lede: 'Datos médicos y datos espaciales, analizados juntos.',
		cta: 'Entrar a la app',
		credit: 'Earthrise · Apolo 8 · 24 dic 1968 · redibujada en ASCII',
	},
	video: {
		label: 'Video de Kha-device 01',
		eyebrow: 'Presentación',
		title: 'Kha-device 01 en 30 segundos',
		play: 'Reproducir',
		pause: 'Pausar',
		mute: 'Silenciar',
		unmute: 'Activar sonido',
		fullscreen: 'Pantalla completa',
		seek: 'Posición del video',
		sound: 'Con sonido',
	},
	different: {
		title: '¿Qué nos hace diferentes?',
		paragraphs: [
			'Un reloj inteligente sigue métricas generales de salud. Nuestro sistema está hecho para el vuelo espacial humano: dos dispositivos en uno, uno para los signos vitales y otro para la radiación ionizante con dosimetría activa.',
			'Tres capacidades de IA convierten esas lecturas en algo que el astronauta puede usar: análisis médico, contexto astronómico y una síntesis que une ambos, incluso cuando la ayuda desde la Tierra no está a mano.',
		],
		hazardsTitle: 'Los cinco peligros de la NASA',
		hazards: ['Radiación espacial', 'Aislamiento y confinamiento', 'Distancia de la Tierra', 'Campos gravitatorios y gravedad alterada', 'Entornos hostiles y cerrados'],
		closing: 'Diseñado en torno a esos cinco peligros: más que un monitor de salud, un sistema de monitoreo y apoyo a la decisión para misiones espaciales.',
		note: 'Es la visión del proyecto. El prototipo actual registra y compara lecturas: no diagnostica ni emite alertas médicas.',
		art: 'Saturno V del Apolo 11 dando la vuelta a la Luna, dibujado en ASCII',
	},
	iss: {
		title: 'Tecnología',
		body: 'Así vamos a construir Kha-device 01: dos dispositivos miden y tres modelos de lenguaje analizan. Dos especialistas, cada uno en lo suyo, y un tercero que resume.',
		credit: 'Estación Espacial Internacional · redibujada en ASCII',
	},
	devices: {
		title: 'Dispositivos',
		intro: 'Los dos dispositivos van sujetos al mismo arnés. Baja para ver cada uno en su sitio.',
		stageLabel:
			'Arnés 3D: la unidad de signos vitales cuelga del vértice de los tirantes y el dosímetro va sobre la banda del pecho; arrastra para girarlo',
		loading: 'Cargando arnés 3D…',
		failed: 'No se pudieron cargar los modelos 3D',
		unsupported: 'Escena 3D no disponible en este navegador',
		hint: 'Arrastra para girar',
		stepsLabel: 'Pasos del arnés',
		steps: ['Dosímetro', 'Signos vitales', 'Espalda'],
		tags: { dosimetro: '01 · Dosímetro', vitales: '02 · Signos vitales' },
		hardwareTitle: 'Hardware',
		dosimeter: {
			eyebrow: 'Dispositivo 1',
			title: 'Crew Active Dosimeter',
			body: 'Dosímetro activo personal. Dos cámaras de iones detectan la radiación ionizante y registran la dosis absorbida en dos rangos de exposición.',
			recordsTitle: 'Registra',
			records: ['Tasa de dosis de radiación', 'Dosis absorbida acumulada', 'Historial de exposición individual', 'Tiempo de exposición registrado'],
			hardware: [
				['2 cámaras DIS · Mirion Technologies', 'Detección'],
				['Cámara DIS de alta resolución', 'Satura a 500–700 mGy'],
				['Cámara DIS de baja resolución', 'Satura a 5–7 Gy'],
				['STM32L432KCU6', 'Microcontrolador'],
				['MB85RS1MT · FRAM', 'Historial de exposición'],
				['TMP117', 'Compensación térmica'],
				['RV-3028-C7', 'Fecha y hora'],
				['CR2032 y 3 × CR1216', 'Alimentación'],
			] as Pair[],
		},
		vitals: {
			eyebrow: 'Dispositivo 2',
			title: 'Signos vitales',
			body: 'Unos datos se miden directamente con sensores; otros se obtienen analizando esas mediciones.',
			measure: 'Medición',
			analysis: 'Análisis',
			groups: [
				{
					system: 'Sistema cardiovascular',
					items: [
						['Frecuencia cardíaca (HR)', 'm'],
						['Variabilidad cardíaca (HRV)', 'a'],
						['Actividad eléctrica cardíaca (ECG)', 'm'],
						['Cambios de patrones del ritmo cardíaco', 'a'],
					],
				},
				{
					system: 'Sistema respiratorio',
					items: [
						['Frecuencia respiratoria', 'm'],
						['Patrones respiratorios', 'a'],
					],
				},
				{ system: 'Oxigenación sanguínea', items: [['Saturación de oxígeno (SpO₂)', 'm']] },
				{
					system: 'Temperatura',
					items: [
						['Temperatura cutánea', 'm'],
						['Variaciones y tendencias térmicas', 'a'],
						['Tendencias de temperatura durante la misión', 'a'],
					],
				},
				{
					system: 'Actividad física y gravedad alterada',
					items: [
						['Actividad física', 'a'],
						['Períodos de inactividad', 'a'],
					],
				},
			] as { system: string; items: Pair[] }[],
			hardware: [
				['MAX86178', 'Pulso, SpO₂ y ECG'],
				['MAX30205', 'Temperatura corporal'],
				['LED y fotodiodos', 'Óptica del pulso'],
				['Electrodos de ECG', 'Una derivación'],
				['Batería LiPo y reguladores', 'Alimentación'],
			] as Pair[],
		},
		back: {
			eyebrow: 'El arnés',
			title: 'Por detrás',
			body: 'Los dos tirantes suben en Y hasta una anilla y un único tirante baja por la espalda hasta una placa donde se une la banda que rodea el pecho. Por delante, los tirantes forman una V sobre las clavículas: en el vértice cuelga la unidad de signos vitales y de ahí baja un tirante, con su cable, hasta el dosímetro, sobre la banda del pecho.',
		},
	},
	flow: {
		title: 'Cómo funciona',
		lead: 'De los sensores al resumen, en seis pasos. Baja y la señal baja contigo.',
		legend: { dose: 'Dosímetro', vitals: 'Signos vitales', temp: 'Temperatura' },
		railLabel: 'Señales del carril',
		inLabel: 'Entra',
		outLabel: 'Sale',
		simulated: 'Datos simulados',
		live: { hr: 'Pulso', spo2: 'SpO₂', temp: 'Piel', dose: 'Dosis', packets: 'Paquetes' },
		steps: [
			{
				title: 'Sensores',
				where: 'Dos dispositivos sobre el cuerpo',
				body: 'El dosímetro detecta la radiación ionizante. El segundo dispositivo lee el pulso y el oxígeno con luz, el corazón con electrodos y la temperatura de la piel.',
				input: 'Radiación, luz, electricidad del corazón y calor de la piel',
				output: 'Señales analógicas',
				parts: [
					['Cámaras DIS', 'Radiación'],
					['LED y fotodiodos', 'Pulso y SpO₂'],
					['Electrodos', 'ECG'],
					['MAX30205', 'Temperatura'],
				],
			},
			{
				title: 'Adquisición',
				where: 'De lo físico a lo digital',
				body: 'Las dos cámaras DIS acumulan la dosis en rangos distintos, así cubren exposiciones bajas y altas. El MAX86178 convierte pulso, SpO₂ y ECG en muestras sincronizadas.',
				input: 'Señales analógicas',
				output: 'Muestras con marca de tiempo',
				parts: [
					['DIS de alta resolución', 'Hasta 500–700 mGy'],
					['DIS de baja resolución', 'Hasta 5–7 Gy'],
					['MAX86178', 'Pulso, SpO₂ y ECG'],
				],
			},
			{
				title: 'Proceso en el dispositivo',
				where: 'Un microcontrolador en cada uno',
				body: 'En el dosímetro, el microcontrolador procesa cada lectura, la corrige por temperatura, le pone fecha y hora y la guarda. En el otro dispositivo, la temperatura del MAX30205 llega directo al microcontrolador y se une al resto.',
				input: 'Muestras y temperatura',
				output: 'Lecturas corregidas, fechadas y guardadas',
				parts: [
					['STM32L432KCU6', 'Procesa las lecturas'],
					['TMP117', 'Compensa la temperatura'],
					['RV-3028-C7', 'Fecha y hora'],
					['MB85RS1MT · FRAM', 'Guarda el historial'],
				],
			},
			{
				title: 'Software de análisis',
				where: 'Fuera de los dispositivos',
				body: 'Aprende la línea base de cada persona. A partir de ella calcula la frecuencia respiratoria, sigue la dosis acumulada y detecta cambios que merecen una alerta.',
				input: 'Lecturas guardadas',
				output: 'Línea base, frecuencia respiratoria y marcas de cambio',
				parts: [
					['Línea base', 'Por persona'],
					['Frecuencia respiratoria', 'Calculada'],
					['Alertas', 'Ante cambios'],
				],
			},
			{
				title: 'Modelos especialistas',
				where: 'Dos modelos de lenguaje',
				body: 'Uno leerá los datos médicos y otro los datos espaciales. Cada uno devolverá su análisis y dirá qué no puede afirmar.',
				input: 'Frases calculadas a partir de las lecturas',
				output: 'Un análisis cada uno, con sus límites',
				parts: [
					['Salud', 'Datos médicos'],
					['Astronomía', 'Datos espaciales'],
				],
			},
			{
				title: 'Síntesis',
				where: 'Un tercer modelo',
				body: 'Unirá los dos análisis en un solo resumen que separa hallazgos, incertidumbres y datos faltantes.',
				input: 'Los dos análisis',
				output: 'Un resumen: hallazgos, incertidumbres y datos faltantes',
				parts: [
					['Hallazgos', ''],
					['Incertidumbres', ''],
					['Datos faltantes', ''],
				],
			},
		] as { title: string; where: string; body: string; input: string; output: string; parts: Pair[] }[],
		cta: { text: 'Mira cómo queda con datos de ejemplo.', button: 'Entrar a la app' },
	},
	models: {
		title: 'Inteligencia artificial',
		items: [
			{
				id: 'salud',
				title: 'Salud',
				engine: 'Llama 3.2 3B · ajuste médico',
				body: 'Un modelo especializado leerá la información médica y devolverá su análisis junto con sus límites. No será un diagnóstico: requiere validación profesional.',
				alt: 'Trazo de electrocardiograma dibujado en ASCII',
			},
			{
				id: 'astronomia',
				title: 'Astronomía',
				engine: 'Llama 3.2 3B · adaptador LoRA de astronomía',
				body: 'Un segundo modelo, afinado en astronomía, analizará los datos espaciales y señalará lo que no puede afirmar.',
				alt: 'Galaxia espiral girando, dibujada en ASCII',
			},
			{
				id: 'sintesis',
				title: 'Síntesis',
				engine: 'IBM Granite 3.3 2B',
				body: 'Un tercer modelo integrará ambos análisis en un resumen que separe hallazgos, incertidumbres y datos faltantes.',
				alt: 'Dos flujos que se unen en uno solo, dibujados en ASCII',
			},
		],
	},
	solar: {
		title: 'Dos lecturas, un resumen',
		body: 'Kha-device 01 recibe información médica y datos espaciales. Cada conjunto lo analiza un modelo especializado, y un tercero combina ambos análisis en un solo resumen.',
	},
	footer: {
		logoLabel: 'Logo del proyecto dibujado en ASCII',
		navLabel: 'Enlaces del proyecto',
		groups: [
			{
				title: 'En esta página',
				links: [
					['Video', '#video'],
					['Qué nos hace diferentes', '#diferentes'],
					['Tecnología', '#tecnologia'],
					['Dispositivos', '#dispositivos'],
					['Cómo funciona', '#funcionamiento'],
					['Inteligencia artificial', '#ia'],
					['Sistema solar', '#sistema-solar'],
				],
			},
			{
				title: 'Proyecto',
				links: [
					['Entrar a la app', 'app'],
					['Repositorio en GitHub', 'repo'],
					['Módulo de IA', 'repo/tree/main/ia'],
				],
			},
			{
				title: 'Modelos',
				links: [
					['Salud · Llama 3.2 3B médico', 'hf:MohamedAhmedAE/Llama-3.2-3B-Instruct-Medical-Finetuned-merged'],
					['Astronomía · LoRA sobre Llama 3.2 3B', 'hf:ojayy/llama32-3b-mmlu-astronomy-lora'],
					['Síntesis · IBM Granite 3.3 2B', 'hf:ibm-granite/granite-3.3-2b-instruct'],
				],
			},
		] as { title: string; links: Pair[] }[],
	},
};

export type Content = typeof es;

const en: Content = {
	meta: {
		title: 'Kha-device 01',
		description: 'Medical data and space data, analysed together.',
	},
	langSwitch: { label: 'Language', es: 'Español', en: 'English' },
	hero: {
		lede: 'Medical data and space data, analysed together.',
		cta: 'Open the app',
		credit: 'Earthrise · Apollo 8 · 24 Dec 1968 · redrawn in ASCII',
	},
	video: {
		label: 'Kha-device 01 video',
		eyebrow: 'Presentation',
		title: 'Kha-device 01 in 30 seconds',
		play: 'Play',
		pause: 'Pause',
		mute: 'Mute',
		unmute: 'Unmute',
		fullscreen: 'Full screen',
		seek: 'Video position',
		sound: 'With sound',
	},
	different: {
		title: 'What makes us different?',
		paragraphs: [
			'A smartwatch tracks general health metrics. Our system is built for human spaceflight: two devices in one, one for vital signs and one for ionizing radiation through active dosimetry.',
			'Three AI capabilities turn those readings into something an astronaut can use: medical analysis, astronomical context, and a synthesis that joins both, even when help from Earth is out of reach.',
		],
		hazardsTitle: "NASA's Five Hazards",
		hazards: ['Space Radiation', 'Isolation and Confinement', 'Distance from Earth', 'Gravity Fields and Altered Gravity', 'Hostile/Closed Environments'],
		closing: 'Designed around those five hazards: more than a health tracker, a health-monitoring and decision-support system for space missions.',
		note: "This is the project vision. Today's prototype records and compares readings: it does not diagnose or issue medical alerts.",
		art: 'Apollo 11 Saturn V circling the Moon, drawn in ASCII',
	},
	iss: {
		title: 'Technology',
		body: 'This is how we will build Kha-device 01: two devices measure and three language models analyse. Two specialists, each at their own task, and a third that summarises.',
		credit: 'International Space Station · redrawn in ASCII',
	},
	devices: {
		title: 'Devices',
		intro: 'Both devices are worn on the same harness. Scroll to see each one in place.',
		stageLabel:
			'3D harness: the vital-signs unit hangs from the vertex of the straps and the dosimeter sits on the chest band; drag to rotate it',
		loading: 'Loading 3D harness…',
		failed: 'The 3D models could not be loaded',
		unsupported: '3D scene not available in this browser',
		hint: 'Drag to rotate',
		stepsLabel: 'Harness steps',
		steps: ['Dosimeter', 'Vital signs', 'Back'],
		tags: { dosimetro: '01 · Dosimeter', vitales: '02 · Vital signs' },
		hardwareTitle: 'Hardware',
		dosimeter: {
			eyebrow: 'Device 1',
			title: 'Crew Active Dosimeter',
			body: 'Active personal dosimeter. Two ion chambers detect ionizing radiation and record the absorbed dose across two exposure ranges.',
			recordsTitle: 'Records',
			records: ['Radiation dose rate', 'Accumulated absorbed dose', 'Individual exposure history', 'Recorded exposure time'],
			hardware: [
				['2 DIS chambers · Mirion Technologies', 'Detection'],
				['High-resolution DIS chamber', 'Saturates at 500–700 mGy'],
				['Low-resolution DIS chamber', 'Saturates at 5–7 Gy'],
				['STM32L432KCU6', 'Microcontroller'],
				['MB85RS1MT · FRAM', 'Exposure history'],
				['TMP117', 'Thermal compensation'],
				['RV-3028-C7', 'Date and time'],
				['CR2032 and 3 × CR1216', 'Power'],
			],
		},
		vitals: {
			eyebrow: 'Device 2',
			title: 'Vital signs',
			body: 'Some data are measured directly by sensors; others are obtained by analysing those measurements.',
			measure: 'Measurement',
			analysis: 'Analysis',
			groups: [
				{
					system: 'Cardiovascular system',
					items: [
						['Heart rate (HR)', 'm'],
						['Heart rate variability (HRV)', 'a'],
						['Cardiac electrical activity (ECG)', 'm'],
						['Changes in heart rhythm patterns', 'a'],
					],
				},
				{
					system: 'Respiratory system',
					items: [
						['Respiratory rate', 'm'],
						['Respiratory patterns', 'a'],
					],
				},
				{ system: 'Blood oxygenation', items: [['Oxygen saturation (SpO₂)', 'm']] },
				{
					system: 'Temperature',
					items: [
						['Skin temperature', 'm'],
						['Thermal variations and trends', 'a'],
						['Temperature trends during the mission', 'a'],
					],
				},
				{
					system: 'Physical activity and altered gravity',
					items: [
						['Physical activity', 'a'],
						['Periods of inactivity', 'a'],
					],
				},
			],
			hardware: [
				['MAX86178', 'Pulse, SpO₂ and ECG'],
				['MAX30205', 'Body temperature'],
				['LED and photodiodes', 'Pulse optics'],
				['ECG electrodes', 'Single lead'],
				['LiPo battery and regulators', 'Power'],
			],
		},
		back: {
			eyebrow: 'The harness',
			title: 'From behind',
			body: 'The two straps rise in a Y to a ring, and a single strap runs down the back to a plate where the chest band joins. In front, the straps form a V over the collarbones: the vital-signs unit hangs from the vertex, and from there a strap, with its cable, runs down to the dosimeter on the chest band.',
		},
	},
	flow: {
		title: 'How it works',
		lead: 'From the sensors to the summary, in six steps. Scroll and the signal travels with you.',
		legend: { dose: 'Dosimeter', vitals: 'Vital signs', temp: 'Temperature' },
		railLabel: 'Signals on the rail',
		inLabel: 'In',
		outLabel: 'Out',
		simulated: 'Simulated data',
		live: { hr: 'Pulse', spo2: 'SpO₂', temp: 'Skin', dose: 'Dose', packets: 'Packets' },
		steps: [
			{
				title: 'Sensors',
				where: 'Two devices on the body',
				body: 'The dosimeter detects ionizing radiation. The second device reads pulse and oxygen with light, the heart with electrodes, and skin temperature.',
				input: 'Radiation, light, the heart’s electricity and skin heat',
				output: 'Analogue signals',
				parts: [
					['DIS chambers', 'Radiation'],
					['LEDs and photodiodes', 'Pulse and SpO₂'],
					['Electrodes', 'ECG'],
					['MAX30205', 'Temperature'],
				],
			},
			{
				title: 'Acquisition',
				where: 'From physical to digital',
				body: 'The two DIS chambers accumulate the dose in different ranges, so they cover low and high exposures. The MAX86178 turns pulse, SpO₂ and ECG into synchronised samples.',
				input: 'Analogue signals',
				output: 'Time-stamped samples',
				parts: [
					['High-resolution DIS', 'Up to 500–700 mGy'],
					['Low-resolution DIS', 'Up to 5–7 Gy'],
					['MAX86178', 'Pulse, SpO₂ and ECG'],
				],
			},
			{
				title: 'On-device processing',
				where: 'A microcontroller in each one',
				body: 'In the dosimeter, the microcontroller processes each reading, corrects it for temperature, adds the date and time and stores it. In the other device, the MAX30205 temperature goes straight to the microcontroller and joins the rest.',
				input: 'Samples and temperature',
				output: 'Corrected, dated, stored readings',
				parts: [
					['STM32L432KCU6', 'Processes the readings'],
					['TMP117', 'Compensates temperature'],
					['RV-3028-C7', 'Date and time'],
					['MB85RS1MT · FRAM', 'Stores the history'],
				],
			},
			{
				title: 'Analysis software',
				where: 'Outside the devices',
				body: 'It learns each person’s baseline. From it, it calculates respiratory rate, tracks the accumulated dose and detects changes that deserve an alert.',
				input: 'Stored readings',
				output: 'Baseline, respiratory rate and change flags',
				parts: [
					['Baseline', 'Per person'],
					['Respiratory rate', 'Calculated'],
					['Alerts', 'On change'],
				],
			},
			{
				title: 'Specialist models',
				where: 'Two language models',
				body: 'One will read the medical data and another the space data. Each will return its analysis and say what it cannot claim.',
				input: 'Sentences computed from the readings',
				output: 'One analysis each, with its limits',
				parts: [
					['Health', 'Medical data'],
					['Astronomy', 'Space data'],
				],
			},
			{
				title: 'Synthesis',
				where: 'A third model',
				body: 'It will merge the two analyses into a single summary that separates findings, uncertainties and missing data.',
				input: 'Both analyses',
				output: 'One summary: findings, uncertainties and missing data',
				parts: [
					['Findings', ''],
					['Uncertainties', ''],
					['Missing data', ''],
				],
			},
		],
		cta: { text: 'See how it looks with sample data.', button: 'Open the app' },
	},
	models: {
		title: 'Artificial intelligence',
		items: [
			{
				id: 'salud',
				title: 'Health',
				engine: 'Llama 3.2 3B · medical fine-tune',
				body: 'A specialised model will read the medical information and return its analysis together with its limits. It will not be a diagnosis: it requires professional validation.',
				alt: 'Electrocardiogram trace drawn in ASCII',
			},
			{
				id: 'astronomia',
				title: 'Astronomy',
				engine: 'Llama 3.2 3B · astronomy LoRA adapter',
				body: 'A second model, tuned on astronomy, will analyse the space data and flag what it cannot claim.',
				alt: 'Spinning spiral galaxy drawn in ASCII',
			},
			{
				id: 'sintesis',
				title: 'Synthesis',
				engine: 'IBM Granite 3.3 2B',
				body: 'A third model will merge both analyses into a summary that separates findings, uncertainties and missing data.',
				alt: 'Two streams joining into one, drawn in ASCII',
			},
		],
	},
	solar: {
		title: 'Two readings, one summary',
		body: 'Kha-device 01 receives medical information and space data. A specialised model analyses each set, and a third combines both analyses into a single summary.',
	},
	footer: {
		logoLabel: 'Project logo drawn in ASCII',
		navLabel: 'Project links',
		groups: [
			{
				title: 'On this page',
				links: [
					['Video', '#video'],
					['What makes us different', '#diferentes'],
					['Technology', '#tecnologia'],
					['Devices', '#dispositivos'],
					['How it works', '#funcionamiento'],
					['Artificial intelligence', '#ia'],
					['Solar system', '#sistema-solar'],
				],
			},
			{
				title: 'Project',
				links: [
					['Open the app', 'app'],
					['GitHub repository', 'repo'],
					['AI module', 'repo/tree/main/ia'],
				],
			},
			{
				title: 'Models',
				links: [
					['Health · medical Llama 3.2 3B', 'hf:MohamedAhmedAE/Llama-3.2-3B-Instruct-Medical-Finetuned-merged'],
					['Astronomy · LoRA on Llama 3.2 3B', 'hf:ojayy/llama32-3b-mmlu-astronomy-lora'],
					['Synthesis · IBM Granite 3.3 2B', 'hf:ibm-granite/granite-3.3-2b-instruct'],
				],
			},
		],
	},
};

export const content: Record<Lang, Content> = { es, en };

/** Dirección de cada idioma: el predeterminado en la raíz y el resto bajo su código. */
export function pathFor(lang: Lang) {
	const base = import.meta.env.BASE_URL.replace(/\/$/, '');
	return lang === DEFAULT_LANG ? `${base}/` : `${base}/${lang}/`;
}

/** Resuelve los destinos simbólicos de los enlaces del pie (app, repo, hf:…). */
export function resolveHref(target: string, lang: Lang, appUrl: string, repo: string) {
	if (target === 'app') return `${appUrl}${appUrl.includes('?') ? '&' : '?'}lang=${lang}`;
	if (target.startsWith('repo')) return `${repo}${target.slice(4)}`;
	if (target.startsWith('hf:')) return `https://huggingface.co/${target.slice(3)}`;
	return target;
}
