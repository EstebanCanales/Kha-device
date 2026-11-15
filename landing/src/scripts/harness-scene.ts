// Escena 3D del arnés: un maniquí con correas de tejido, hebillas metálicas y los dos dispositivos acoplados.
// El scroll arma el arnés (las correas se tienden, las piezas encajan, los dispositivos vuelan a su sitio) y la cámara
// enfoca el dispositivo cuya ficha se está leyendo. También se puede arrastrar para girar el arnés.
import {
	ACESFilmicToneMapping,
	BufferGeometry,
	CanvasTexture,
	CatmullRomCurve3,
	Color,
	DirectionalLight,
	DoubleSide,
	Float32BufferAttribute,
	Group,
	HemisphereLight,
	MathUtils,
	Mesh,
	MeshStandardMaterial,
	Object3D,
	PerspectiveCamera,
	PMREMGenerator,
	Quaternion,
	RepeatWrapping,
	Scene,
	SphereGeometry,
	SRGBColorSpace,
	BoxGeometry,
	CylinderGeometry,
	TorusGeometry,
	TubeGeometry,
	Vector2,
	Vector3,
	WebGLRenderer,
	Box3,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const smooth = (x: number) => x * x * (3 - 2 * x);
const easeOut = (x: number) => 1 - (1 - x) ** 3;
const easeBack = (x: number) => {
	const c = 1.70158;
	return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2;
};

/* ---------- el cuerpo ---------- */

// Perfil del torso (radio según la altura); se escala a una elipse más ancha que honda.
const PROFILE: [number, number][] = [
	[-1.3, 0], [-1.28, 0.86], [-1.0, 0.97], [-0.4, 0.9], [0, 0.88], [0.5, 0.96], [0.85, 1.02], [1.1, 0.9], [1.22, 0.55], [1.3, 0.2], [1.5, 0.17], [1.52, 0],
];
const HALF_WIDTH = 0.95;
const HALF_DEPTH = 0.56;
const BAND_Y = -0.25; // altura de la banda del pecho

function radiusAt(y: number) {
	for (let i = 1; i < PROFILE.length; i++) {
		const [y0, r0] = PROFILE[i - 1], [y1, r1] = PROFILE[i];
		if (y <= y1) return MathUtils.lerp(r0, r1, clamp01((y - y0) / (y1 - y0 || 1)));
	}
	return 0.2;
}

/** Punto sobre el pecho (side 1) o la espalda (side -1), separado `off` de la piel. */
function onBody(x: number, y: number, off: number, side = 1) {
	const r = radiusAt(y);
	const a = HALF_WIDTH * r, b = HALF_DEPTH * r;
	return new Vector3(x, y, side * (b * Math.sqrt(Math.max(0, 1 - (x / a) ** 2)) + off));
}

/** Dirección que sale de la piel en ese punto. */
function bodyNormal(p: Vector3) {
	const r = radiusAt(p.y);
	const a = HALF_WIDTH * r, b = HALF_DEPTH * r;
	const n = new Vector3(p.x / (a * a), p.y > 1.05 ? (p.y - 1.05) * 2 : 0, p.z / (b * b));
	return n.normalize();
}

/* ---------- correas ---------- */

/** Tejido negro con trama en espiga y costura dorada en los dos bordes. */
function webbingTexture() {
	const canvas = document.createElement('canvas');
	canvas.width = 256;
	canvas.height = 64;
	const g = canvas.getContext('2d')!;
	g.fillStyle = '#141923';
	g.fillRect(0, 0, 256, 64);
	g.strokeStyle = 'rgba(255,255,255,0.06)';
	g.lineWidth = 2;
	for (let x = -64; x < 320; x += 8) {
		g.beginPath();
		g.moveTo(x, 12);
		g.lineTo(x + 24, 52);
		g.stroke();
		g.beginPath();
		g.moveTo(x + 24, 12);
		g.lineTo(x, 52);
		g.stroke();
	}
	g.fillStyle = 'rgba(0,0,0,0.4)';
	g.fillRect(0, 0, 256, 5);
	g.fillRect(0, 59, 256, 5);
	g.strokeStyle = '#d8b46a';
	g.lineWidth = 2.4;
	g.setLineDash([11, 7]);
	for (const y of [11, 53]) {
		g.beginPath();
		g.moveTo(0, y);
		g.lineTo(256, y);
		g.stroke();
	}
	const texture = new CanvasTexture(canvas);
	texture.wrapS = RepeatWrapping;
	texture.colorSpace = SRGBColorSpace;
	texture.anisotropy = 8;
	return texture;
}

/** Cinta plana que sigue una curva pegada al cuerpo. Se dibuja por tramos para poder «tenderla» con el scroll. */
function ribbon(points: Vector3[], width: number, thick: number, material: MeshStandardMaterial, closed = false) {
	const segments = 160;
	const curve = new CatmullRomCurve3(points, closed, 'centripetal');
	const length = curve.getLength();
	const pos: number[] = [], uv: number[] = [], index: number[] = [];
	const corners: [number, number, number][] = [[-1, 1, 0], [1, 1, 1], [1, -1, 1], [-1, -1, 0]];
	for (let i = 0; i <= segments; i++) {
		const t = i / segments;
		const p = curve.getPointAt(t);
		const tan = curve.getTangentAt(t).normalize();
		const side = new Vector3().crossVectors(tan, bodyNormal(p)).normalize();
		const up = new Vector3().crossVectors(side, tan).normalize();
		for (const [sx, sn, v] of corners) {
			pos.push(p.x + (side.x * sx * width) / 2 + (up.x * sn * thick) / 2, p.y + (side.y * sx * width) / 2 + (up.y * sn * thick) / 2, p.z + (side.z * sx * width) / 2 + (up.z * sn * thick) / 2);
			uv.push((t * length) / (width * 4), v);
		}
	}
	for (let i = 0; i < segments; i++)
		for (let k = 0; k < 4; k++) {
			const a = i * 4 + k, b = i * 4 + ((k + 1) % 4), c = (i + 1) * 4 + k, d = (i + 1) * 4 + ((k + 1) % 4);
			index.push(a, b, c, b, d, c);
		}
	const geometry = new BufferGeometry();
	geometry.setAttribute('position', new Float32BufferAttribute(pos, 3));
	geometry.setAttribute('uv', new Float32BufferAttribute(uv, 2));
	geometry.setIndex(index);
	geometry.computeVertexNormals();
	const mesh = new Mesh(geometry, material);
	mesh.userData.segments = segments;
	return mesh;
}

const reveal = (m: Mesh, f: number) => {
	m.geometry.setDrawRange(0, Math.floor(clamp01(f) * m.userData.segments) * 24);
	m.visible = f > 0.001;
};

/* ---------- escena ---------- */

interface Placement {
	group: Group;
	at: Vector3;
	from: Vector3;
	base: Quaternion;
	spin: number;
	/** Dónde sale el rótulo, respecto al dispositivo y en el espacio del arnés. */
	tag: Vector3;
}

export function mountHarness(stage: HTMLElement, urls: { dosimetro: string; vitales: string }) {
	const status = stage.querySelector<HTMLElement>('.harness__status');
	const say = (text: string) => status && ((status.textContent = text), (status.hidden = !text));
	const reduced = matchMedia('(prefers-reduced-motion: reduce)');
	const articles = [...document.querySelectorAll<HTMLElement>('.device[data-device]')];
	const tags = new Map(Array.from(stage.querySelectorAll<HTMLElement>('[data-tag]'), (el) => [el.dataset.tag!, el]));

	let renderer: WebGLRenderer;
	try {
		renderer = new WebGLRenderer({ antialias: true, alpha: true });
	} catch {
		stage.dataset.failed = 'true';
		say(stage.dataset.unsupported ?? '');
		return;
	}
	renderer.outputColorSpace = SRGBColorSpace;
	renderer.toneMapping = ACESFilmicToneMapping;
	renderer.toneMappingExposure = 1.1;
	renderer.setClearColor(0x000000, 0);
	const canvas = renderer.domElement;
	canvas.className = 'harness__canvas';
	canvas.setAttribute('aria-hidden', 'true');
	stage.prepend(canvas);

	const scene = new Scene();
	// Entorno de estudio: da reflejos a los metales y a los acabados de los dispositivos.
	const pmrem = new PMREMGenerator(renderer);
	scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
	scene.environmentIntensity = 0.75;
	const camera = new PerspectiveCamera(32, 1, 0.1, 60);
	const key = new DirectionalLight('#ffffff', 2.4);
	key.position.set(-3, 4, 5);
	const rim = new DirectionalLight('#6fa8ff', 2.6);
	rim.position.set(4, 2, -4);
	const back = new DirectionalLight('#ffffff', 1.6); // luz desde atrás-izquierda: la vista posterior no queda a oscuras
	back.position.set(-3, 3, -5);
	scene.add(key, rim, back, new HemisphereLight('#9fb2d8', '#0b1124', 0.55));

	const rig = new Group(); // todo el arnés gira junto
	scene.add(rig);

	const webbing = new MeshStandardMaterial({ map: webbingTexture(), roughness: 0.88, metalness: 0, side: DoubleSide });
	const metal = new MeshStandardMaterial({ color: '#d6dbe6', metalness: 1, roughness: 0.26 });
	const wire = new MeshStandardMaterial({ color: '#f28c28', roughness: 0.38, metalness: 0.1 });

	/*
	 * Diseño del arnés (según el boceto del proyecto):
	 *  - Frente: dos tirantes bajan de los hombros en V hasta el pecho; en el vértice cuelga el dosímetro y de ahí baja
	 *    un tirante por el esternón, con un cable naranja, hasta la unidad de signos vitales sobre la banda del pecho.
	 *  - Espalda: los dos tirantes suben en Y hasta una anilla y un único tirante baja hasta una placa de la banda.
	 */
	const straps: Mesh[] = [];
	// Un tirante por hombro: del vértice delantero, sobre el hombro, a la anilla de la espalda.
	for (const s of [-1, 1]) {
		straps.push(
			ribbon(
				[
					onBody(0, 0.97, 0.035),
					onBody(s * 0.22, 1.05, 0.035),
					onBody(s * 0.45, 1.15, 0.035),
					onBody(s * 0.6, 1.19, 0.04),
					onBody(s * 0.45, 1.14, 0.035, -1),
					onBody(s * 0.22, 1.01, 0.035, -1),
					onBody(0, 0.93, 0.035, -1),
				],
				0.09, 0.028, webbing,
			),
		);
	}
	// Tirante vertical del esternón y tirante vertical de la espalda.
	straps.push(ribbon([0.95, 0.6, 0.2, -0.05, BAND_Y].map((y) => onBody(0, y, 0.04)), 0.09, 0.03, webbing));
	straps.push(ribbon([0.92, 0.6, 0.2, -0.05, BAND_Y].map((y) => onBody(0, y, 0.04, -1)), 0.09, 0.03, webbing));
	// Banda que rodea el pecho.
	const band = ribbon(
		Array.from({ length: 40 }, (_, i) => {
			const th = (i / 40) * Math.PI * 2, r = radiusAt(BAND_Y);
			return new Vector3((HALF_WIDTH * r + 0.04) * Math.sin(th), BAND_Y, (HALF_DEPTH * r + 0.04) * Math.cos(th));
		}),
		0.09, 0.026, webbing, true,
	);
	straps.push(band);
	straps.forEach((m) => rig.add(m));

	// Herrajes: clip del vértice, anilla de la espalda, placa trasera y conector, orientados a la curva del cuerpo.
	const hardware = new Group();
	rig.add(hardware);
	const place = (obj: Object3D, p: Vector3) => {
		obj.position.copy(p);
		obj.lookAt(p.clone().add(bodyNormal(p)));
		hardware.add(obj);
		return obj;
	};
	const plate = (w: number, h: number, d: number, mat = metal) => new Mesh(new RoundedBoxGeometry(w, h, d, 4, Math.min(w, h) * 0.14), mat);
	place(new Mesh(new TorusGeometry(0.075, 0.016, 14, 32), metal), onBody(0, 0.93, 0.09, -1)); // anilla de la espalda
	place(plate(0.2, 0.11, 0.04, metal), onBody(0, BAND_Y, 0.07, -1)); // placa trasera de la banda
	place(plate(0.1, 0.045, 0.04), onBody(0, BAND_Y + 0.185, 0.065)); // conector sobre el dosímetro
	// Cable naranja que acompaña al tirante del esternón, con algo de holgura.
	const cable = new Mesh(
		new TubeGeometry(new CatmullRomCurve3([onBody(0.06, 0.54, 0.06), onBody(0.1, 0.25, 0.062), onBody(0.075, 0.05, 0.062), onBody(0.05, BAND_Y + 0.16, 0.065)]), 48, 0.012, 8),
		wire,
	);
	hardware.add(cable);

	// Costuras de refuerzo (cajas con X) donde se cruzan los tirantes y en las uniones con la banda.
	const stitch = new MeshStandardMaterial({ color: '#d8b46a', roughness: 0.6, metalness: 0 });
	const box = (c: Vector3, w: number, h: number) => {
		const g = new Group();
		for (const [dx, dy, len, rot] of [[0, h / 2, w, 0], [0, -h / 2, w, 0], [-w / 2, 0, h, Math.PI / 2], [w / 2, 0, h, Math.PI / 2], [0, 0, Math.hypot(w, h), Math.atan2(h, w)], [0, 0, Math.hypot(w, h), -Math.atan2(h, w)]] as number[][]) {
			const m = new Mesh(new BoxGeometry(len, 0.006, 0.004), stitch);
			m.position.set(dx, dy, 0);
			m.rotation.z = rot;
			g.add(m);
		}
		g.position.copy(c);
		g.lookAt(c.clone().add(bodyNormal(c)));
		hardware.add(g);
	};
	box(onBody(0, BAND_Y + 0.3, 0.07), 0.07, 0.07);
	box(onBody(0, BAND_Y + 0.3, 0.07, -1), 0.07, 0.07);
	box(onBody(0, BAND_Y + 0.1, 0.07, -1), 0.07, 0.08);
	box(onBody(0, 0.78, 0.07), 0.07, 0.07);

	// Detalle fino: todo cuelga del grupo de herrajes, así aparece con la misma animación de montaje.
	const bolt = new MeshStandardMaterial({ color: '#8d96a8', metalness: 1, roughness: 0.35 });
	// Hebillas ajustadoras de los tirantes verticales, delante y detrás.
	place(plate(0.11, 0.075, 0.035), onBody(0, 0.1, 0.075));
	place(plate(0.11, 0.075, 0.035), onBody(0, 0.1, 0.075, -1));
	// Anillas D en los extremos de la banda, para sujetar el cable y las herramientas.
	for (const s of [-1, 1]) place(new Mesh(new TorusGeometry(0.045, 0.011, 10, 24), metal), onBody(s * 0.82, BAND_Y, 0.075));
	// Cierre lateral de la banda: dos mitades de polímero con un pasador.
	place(plate(0.12, 0.15, 0.04, metal), onBody(0.93, BAND_Y, 0.07, 1));
	place(plate(0.05, 0.05, 0.05, metal), onBody(0.93, BAND_Y, 0.095, 1));
	// Remaches en las esquinas de la placa trasera.
	for (const dx of [-0.085, 0.085]) for (const dy of [-0.055, 0.055]) {
		const rivet = place(new Mesh(new CylinderGeometry(0.011, 0.011, 0.02, 12), bolt), onBody(dx, BAND_Y + dy, 0.12, -1));
		rivet.rotateX(Math.PI / 2);
	}
	// Clips que sujetan el cable naranja al tirante, y un pasacables junto al dosímetro.
	for (const y of [0.2, 0.0]) place(plate(0.045, 0.03, 0.03, metal), onBody(0.07, y, 0.095));
	/* ---------- dispositivos ---------- */

	const devices: Record<string, Placement> = {};
	const leds: MeshStandardMaterial[] = [];
	const loader = new GLTFLoader();
		// Un solo acabado para los dos dispositivos: aluminio cepillado, sin partes oscuras.
	const brushed = { light: new Color('#b4bccc'), dark: new Color('#8f98ab') };

	function mountDevice(name: string, url: string, width: number, at: Vector3, from: Vector3, finish: typeof anodized, metalness: number, tag: Vector3, roll = 0) {
		return loader.loadAsync(url).then((gltf) => {
			const model = gltf.scene;
			const box = new Box3().setFromObject(model);
			const size = box.getSize(new Vector3()), center = box.getCenter(new Vector3());
			// Cada GLB trae una rotación de -90° en X en su nodo raíz (viene de un STL con Z hacia arriba): ya cargado,
			// la placa es plana en XY y su relieve mira hacia -Z. Se centra, se escala por su lado mayor y se voltea
			// para que el relieve mire hacia afuera del pecho.
			const major = Math.max(size.x, size.y);
			const aspect = size.y / major;
			const k = width / major;
			model.position.sub(center).multiplyScalar(k);
			model.scale.setScalar(k);
			const flat = new Group();
			flat.rotation.y = Math.PI;
			flat.rotation.z = roll; // giro en su propio plano: el de signos vitales va vertical, con la punta hacia arriba
			flat.add(model);

			// Acabados: la cara con relieve en metal anodizado o cepillado, el cuerpo en polímero oscuro.
			const mats = new Set<MeshStandardMaterial>();
			model.traverse((o) => (o as Mesh).isMesh && [(o as Mesh).material].flat().forEach((m) => mats.add(m as MeshStandardMaterial)));
			const lum = (m: MeshStandardMaterial) => m.color.r + m.color.g + m.color.b;
			const top = Math.max(...[...mats].map(lum));
			mats.forEach((m) => {
				const light = lum(m) >= top - 1e-3;
				m.color.copy(light ? finish.light : finish.dark);
				m.metalness = light ? metalness : 0.12;
				m.roughness = light ? 0.34 : 0.55;
				m.envMapIntensity = light ? 1.5 : 0.8;
			});

			// Un piloto de estado que parpadea, sin marcos ni placas alrededor.
			const mount = new Group();
			const ledMat = new MeshStandardMaterial({ color: '#000', emissive: '#78dcd2', emissiveIntensity: 2 });
			leds.push(ledMat);
			const led = new Mesh(new SphereGeometry(0.02, 16, 12), ledMat);
			led.position.set(...(roll ? [aspect * width * 0.4, width * 0.4] : [width * 0.4, aspect * width * 0.4]), 0.03);
			mount.add(flat, led);

			const group = new Group();
			group.add(mount);
			group.position.copy(at);
			group.lookAt(at.clone().add(bodyNormal(at)));
			rig.add(group);
			devices[name] = { group, at: at.clone(), from, base: group.quaternion.clone(), spin: name === 'dosimetro' ? 2.4 : -2.0, tag };
		});
	}

	Promise.all([
		// Dosímetro (amarillo) sobre la banda, en el pecho; unidad de signos vitales (plateada) vertical bajo el vértice de la V.
		mountDevice('dosimetro', urls.dosimetro, 0.17, onBody(0, BAND_Y, 0.06), new Vector3(-3.2, 0.4, 2.6), brushed, 0.9, new Vector3(-0.45, -0.1, 0.1)),
		mountDevice('vitales', urls.vitales, 0.52, onBody(0, 0.8, 0.035), new Vector3(3.0, 1.6, 2.8), brushed, 0.9, new Vector3(0.36, 0.12, 0.1), -Math.PI / 2),
	]).then(
		() => {
			say('');
			canvas.classList.add('is-ready');
			wake();
		},
		() => say(stage.dataset.failed ?? ''),
	);

/* ---------- cámara y scroll ---------- */

	interface View {
		pos: Vector3;
		look: Vector3;
		yaw: number;
	}
	const v3 = (x: number, y: number, z: number) => new Vector3(x, y, z);
	// Vistas: general, dosímetro (en el vértice de los tirantes), unidad de pecho y la espalda (el arnés da media vuelta).
	const VIEWS: Record<string, View> = {
		overview: { pos: v3(0, 0.2, 6.5), look: v3(0, 0.15, 0), yaw: 0.16 },
		dosimetro: { pos: v3(0.2, 0.2, 5.5), look: v3(0, 0.1, 0.3), yaw: -0.1 },
		vitales: { pos: v3(-0.1, 0.55, 4.5), look: v3(0, 0.3, 0.3), yaw: 0.1 },
		espalda: { pos: v3(0, 0.25, 6.1), look: v3(0, 0.2, 0), yaw: Math.PI + 0.08 },
	};
	const ORDER = ['dosimetro', 'vitales', 'espalda'];
	const mix = (a: View, b: View, k: number): View => ({ pos: a.pos.clone().lerp(b.pos, k), look: a.look.clone().lerp(b.look, k), yaw: MathUtils.lerp(a.yaw, b.yaw, k) });

	// Cuánto está «en foco» cada ficha: 1 cuando su centro cruza el centro de la pantalla.
	function focus(el: HTMLElement) {
		const r = el.getBoundingClientRect();
		return clamp01(1 - Math.abs(r.top + r.height * 0.35 - innerHeight * 0.5) / (innerHeight * 0.6));
	}

	let aspectPush = 1, assemble = 0;
	const camPos = VIEWS.overview.pos.clone(), camLook = VIEWS.overview.look.clone();
	let yaw = VIEWS.overview.yaw, dragYaw = 0, dragging = false, lastX = 0;
	let visible = false, raf = 0, last = performance.now();
	const tmp = new Vector3(), spinQ = new Quaternion(), Z = new Vector3(0, 0, 1);

	function frame(now = performance.now()) {
		raf = 0;
		const dt = Math.min(0.05, (now - last) / 1000);
		last = now;
		const calm = reduced.matches;

		// Armado: ocurre mientras la escena sube hasta quedar fija en pantalla.
		const top = stage.getBoundingClientRect().top;
		assemble = calm ? 1 : clamp01((innerHeight - top) / (innerHeight * 0.9));
		// Orden de armado: la banda rodea el pecho, los tirantes bajan de los hombros y los verticales los unen.
		const [leftStrap, rightStrap, frontStrap, backStrap, bandStrap] = straps;
		reveal(bandStrap, easeOut(clamp01(assemble / 0.5)));
		reveal(leftStrap, easeOut(clamp01((assemble - 0.08) / 0.5)));
		reveal(rightStrap, easeOut(clamp01((assemble - 0.08) / 0.5)));
		reveal(frontStrap, easeOut(clamp01((assemble - 0.3) / 0.3)));
		reveal(backStrap, easeOut(clamp01((assemble - 0.3) / 0.3)));
		hardware.scale.setScalar(Math.max(0.0001, easeBack(clamp01((assemble - 0.4) / 0.3))));
		hardware.visible = assemble > 0.4;
		for (const d of Object.values(devices)) {
			const e = clamp01((assemble - 0.55) / 0.45);
			d.group.visible = e > 0;
			d.group.position.lerpVectors(d.from, d.at, easeOut(e));
			d.group.quaternion.copy(d.base).multiply(spinQ.setFromAxisAngle(Z, (1 - easeOut(e)) * d.spin));
			d.group.scale.setScalar(MathUtils.lerp(0.4, 1, easeOut(e)));
		}

		// Cámara: se acerca al dispositivo de la ficha que se lee y vuelve a la vista general entre fichas.
		const w = ORDER.map((_, i) => (articles[i] ? focus(articles[i]) : 0));
		const [wd, wv] = w;
		const near = Math.max(...w), total = w.reduce((a, b) => a + b, 0);
		// Media ponderada de las vistas cuyas fichas están en pantalla, y de ahí hacia la vista general según cuánto foco hay.
		let picked = VIEWS.overview;
		if (total > 0) {
			picked = { pos: new Vector3(), look: new Vector3(), yaw: 0 };
			ORDER.forEach((name, i) => {
				const f = w[i] / total;
				picked.pos.addScaledVector(VIEWS[name].pos, f);
				picked.look.addScaledVector(VIEWS[name].look, f);
				picked.yaw += VIEWS[name].yaw * f;
			});
		}
		const view = mix(VIEWS.overview, picked, smooth(clamp01(near * 1.25)));
		const k = calm ? 1 : 1 - Math.exp(-dt * 4.5);
		camPos.lerp(view.pos, k);
		camLook.lerp(view.look, k);
		yaw += (view.yaw + dragYaw - yaw) * k;
		if (!dragging) dragYaw *= Math.exp(-dt * 0.5);
		rig.rotation.y = yaw + (calm ? 0 : Math.sin(now / 2600) * 0.04);
		camera.position.copy(camPos).setZ(camPos.z * aspectPush);
		camera.lookAt(camLook);

		// Pilotos de estado y rótulos que siguen a cada dispositivo.
		leds.forEach((m, i) => (m.emissiveIntensity = 1.4 + Math.sin(now / 420 + i * 2) * 0.9));
		const rect = stage.getBoundingClientRect();
		for (const [name, el] of tags) {
			const d = devices[name];
			if (!d) continue;
			const p = rig.localToWorld(tmp.copy(d.group.position).add(d.tag)).project(camera);
			const w = name === 'dosimetro' ? wd : wv;
			// El rótulo del dispositivo alto va a su izquierda para no salirse del encuadre.
			el.style.transform = `translate(${(p.x * 0.5 + 0.5) * rect.width}px, ${(-p.y * 0.5 + 0.5) * rect.height}px) translateX(${d.tag.x < 0 ? '-100%' : '0'})`;
			el.style.opacity = String(clamp01((w - 0.3) * 2.2));
		}

		renderer.render(scene, camera);
		if (visible && !document.hidden && !calm) raf = requestAnimationFrame(frame);
	}
	const wake = () => {
		if (!raf) raf = requestAnimationFrame(frame);
	};

	function resize() {
		const { clientWidth: w, clientHeight: h } = stage;
		if (!w || !h) return;
		renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
		renderer.setSize(w, h, false);
		camera.aspect = w / h;
		// En vertical hay que alejar la cámara para que quepa el ancho del arnés.
		aspectPush = camera.aspect < 1 ? 1 + (1 - camera.aspect) * 0.9 : 1;
		camera.updateProjectionMatrix();
	}

	new ResizeObserver(() => (resize(), wake())).observe(stage);
	new IntersectionObserver(([e]) => {
		visible = e.isIntersecting;
		if (visible) {
			last = performance.now();
			wake();
		}
	}).observe(stage);
	document.addEventListener('visibilitychange', wake);
	// Con menos movimiento no hay bucle: se dibuja de nuevo al desplazarse o arrastrar.
	addEventListener('scroll', () => reduced.matches && visible && wake(), { passive: true });

	stage.addEventListener('pointerdown', (e) => {
		dragging = true;
		lastX = e.clientX;
		stage.setPointerCapture(e.pointerId);
		stage.classList.add('is-dragging');
	});
	stage.addEventListener('pointermove', (e) => {
		if (!dragging) return;
		dragYaw = MathUtils.clamp(dragYaw + (e.clientX - lastX) * 0.012, -1.6, 1.6);
		lastX = e.clientX;
		wake();
	});
	const end = () => {
		dragging = false;
		stage.classList.remove('is-dragging');
	};
	stage.addEventListener('pointerup', end);
	stage.addEventListener('pointercancel', end);
}
