// Visor 3D para los modelos GLB de los dispositivos.
// El modelo gira, se inclina y se acerca según cuánto se ha desplazado la página; también se arrastra con el dedo o el ratón.
import {
	AmbientLight,
	Box3,
	Color,
	DirectionalLight,
	Group,
	HemisphereLight,
	MathUtils,
	Mesh,
	MeshStandardMaterial,
	PerspectiveCamera,
	Scene,
	SRGBColorSpace,
	ACESFilmicToneMapping,
	Vector3,
	WebGLRenderer,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const smooth = (x: number) => x * x * (3 - 2 * x);

/** Colores de la web aplicados al modelo: la pieza clara en regolito, la oscura en azul noche. */
const LIGHT = new Color('#cfd3dc');
const DARK = new Color('#1a2138');

/** Cuánto ha avanzado el elemento por la ventana: 0 al entrar por abajo, 0,5 centrado, 1 al salir por arriba. */
function scrollProgress(el: HTMLElement) {
	const r = el.getBoundingClientRect();
	return clamp01(1 - (r.top + r.height) / (innerHeight + r.height));
}

/**
 * `track` es el bloque cuyo paso por la pantalla marca la animación. El modelo va fijo mientras se lee la lista,
 * así que su propia posición no cambia: se mide el bloque que lo contiene.
 */
export function mountModel(host: HTMLElement, url: string, track: HTMLElement = host) {
	const status = host.querySelector<HTMLElement>('.slot__pending');
	const say = (text: string) => status && ((status.textContent = text), (status.hidden = !text));
	const reduced = matchMedia('(prefers-reduced-motion: reduce)');

	let renderer: WebGLRenderer;
	try {
		renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
	} catch {
		say('Modelo 3D no disponible en este navegador');
		return;
	}
	renderer.outputColorSpace = SRGBColorSpace;
	renderer.toneMapping = ACESFilmicToneMapping;
	renderer.toneMappingExposure = 1.05;
	renderer.setClearColor(0x000000, 0);
	const canvas = renderer.domElement;
	canvas.className = 'model__canvas';
	canvas.setAttribute('aria-hidden', 'true');
	host.append(canvas);

	const scene = new Scene();
	const camera = new PerspectiveCamera(30, 1, 0.1, 100);
	// Una luz principal desde arriba a la izquierda, un contraluz frío y un relleno suave.
	const key = new DirectionalLight('#ffffff', 3.1);
	key.position.set(-3, 5, 4);
	const rim = new DirectionalLight('#6fa8ff', 2.2);
	rim.position.set(4, 2, -4);
	scene.add(key, rim, new HemisphereLight('#aab6d6', '#0b1124', 0.9), new AmbientLight('#ffffff', 0.25));

	const pivot = new Group();
	scene.add(pivot);
	let fit = 6; // distancia de cámara que encuadra el modelo
	let ready = false;

	new GLTFLoader().load(
		url,
		(gltf) => {
			const model = gltf.scene;
			const box = new Box3().setFromObject(model);
			const size = box.getSize(new Vector3());
			const center = box.getCenter(new Vector3());
			// Se centra y se escala para que su lado mayor mida 2,4 unidades, sea cual sea la unidad original.
			const scale = 2.4 / Math.max(size.x, size.z, size.y);
			model.position.sub(center).multiplyScalar(scale);
			model.scale.setScalar(scale);
			pivot.add(model);

			// La pieza más clara del modelo toma el color regolito; la más oscura, el azul noche.
			const materials = new Set<MeshStandardMaterial>();
			model.traverse((o) => (o as Mesh).isMesh && [(o as Mesh).material].flat().forEach((m) => materials.add(m as MeshStandardMaterial)));
			const lum = (m: MeshStandardMaterial) => m.color.r + m.color.g + m.color.b;
			const brightest = Math.max(...[...materials].map(lum));
			materials.forEach((m) => {
				const light = lum(m) >= brightest - 1e-3;
				m.color.copy(light ? LIGHT : DARK);
				m.metalness = light ? 0.35 : 0.2;
				m.roughness = light ? 0.5 : 0.65;
			});

			const radius = Math.hypot(size.x, size.y, size.z) * scale * 0.5;
			fit = (radius / Math.sin(MathUtils.degToRad(camera.fov / 2))) * 1.08;
			ready = true;
			say('');
			canvas.classList.add('is-ready');
			resize();
			frame();
		},
		undefined,
		() => say('No se pudo cargar el modelo 3D'),
	);

	function resize() {
		const { clientWidth: w, clientHeight: h } = host;
		if (!w || !h) return;
		renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
		renderer.setSize(w, h, false);
		camera.aspect = w / h;
		camera.updateProjectionMatrix();
	}

	// Estado suavizado: el modelo sigue al scroll con un retardo corto en vez de saltar.
	let yaw = 0, pitch = 0.9, zoom = 1;
	let dragYaw = 0, dragPitch = 0, dragging = false, lastX = 0, lastY = 0;
	let visible = false, raf = 0, last = performance.now();

	function frame(now = performance.now()) {
		raf = 0;
		if (!ready) return;
		const dt = Math.min(0.05, (now - last) / 1000);
		last = now;
		const calm = reduced.matches;
		const p = calm ? 0.5 : scrollProgress(track);
		// Gira medio giro mientras pasa por la pantalla, se levanta de la vista casi cenital a una oblicua y se acerca al centro.
		const targetYaw = MathUtils.lerp(-1.15, 1.15, p) + dragYaw;
		const targetPitch = MathUtils.lerp(1.0, 0.5, smooth(p)) + dragPitch;
		const targetZoom = 1 - 0.09 * Math.sin(Math.PI * p);
		const k = calm ? 1 : 1 - Math.exp(-dt * 7);
		yaw += (targetYaw - yaw) * k;
		pitch += (targetPitch - pitch) * k;
		zoom += (targetZoom - zoom) * k;
		// Al soltar, el giro del usuario vuelve poco a poco a la animación del scroll.
		if (!dragging && !calm) {
			dragYaw *= Math.exp(-dt * 0.6);
			dragPitch *= Math.exp(-dt * 0.6);
		}
		const bob = calm ? 0 : Math.sin(now / 1100) * 0.025;
		pivot.rotation.set(0, yaw, 0);
		pivot.position.y = bob;
		const d = fit * zoom;
		camera.position.set(0, Math.sin(pitch) * d, Math.cos(pitch) * d);
		camera.lookAt(0, 0, 0);
		renderer.render(scene, camera);
		if (visible && !document.hidden && !calm) raf = requestAnimationFrame(frame);
	}
	const wake = () => {
		if (ready && !raf) raf = requestAnimationFrame(frame);
	};

	new ResizeObserver(() => (resize(), wake())).observe(host);
	new IntersectionObserver(([e]) => {
		visible = e.isIntersecting;
		if (visible) {
			last = performance.now();
			wake();
		}
	}).observe(host);
	document.addEventListener('visibilitychange', wake);
	// Con menos movimiento no hay bucle: se vuelve a dibujar al desplazarse o arrastrar.
	addEventListener('scroll', () => reduced.matches && visible && wake(), { passive: true });

	// Arrastrar para girar: horizontal = giro, vertical = inclinación.
	host.addEventListener('pointerdown', (e) => {
		dragging = true;
		lastX = e.clientX;
		lastY = e.clientY;
		host.setPointerCapture(e.pointerId);
		host.classList.add('is-dragging');
	});
	host.addEventListener('pointermove', (e) => {
		if (!dragging) return;
		dragYaw += (e.clientX - lastX) * 0.012;
		dragPitch = MathUtils.clamp(dragPitch + (e.clientY - lastY) * 0.008, -0.6, 0.5);
		lastX = e.clientX;
		lastY = e.clientY;
		wake();
	});
	const end = () => {
		dragging = false;
		host.classList.remove('is-dragging');
	};
	host.addEventListener('pointerup', end);
	host.addEventListener('pointercancel', end);
}
