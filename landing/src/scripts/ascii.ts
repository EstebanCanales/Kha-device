// Motor compartido para las escenas ASCII: rampa de símbolos, ruido y ciclo de dibujo.

export const BG = '#070b17';
export const FONT = '"IBM Plex Mono", ui-monospace, Menlo, monospace';

// Solo símbolos, de menos a más tinta. Sin letras ni números.
export const RAMP = ' .`\',:;"^~-_!+<>=?/\\|)(][}{*%#&$@';

export const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

export const smooth = (a: number, b: number, x: number) => {
	const k = clamp01((x - a) / (b - a));
	return k * k * (3 - 2 * k);
};

export const glyph = (b: number) => RAMP[Math.round(clamp01(b) * (RAMP.length - 1))];

export function hash(x: number, y: number, z: number) {
	let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(z, 2147483647);
	h = Math.imul(h ^ (h >>> 13), 1274126177);
	return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

export function noise(x: number, y: number, z: number) {
	const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
	let fx = x - xi, fy = y - yi, fz = z - zi;
	fx = fx * fx * (3 - 2 * fx);
	fy = fy * fy * (3 - 2 * fy);
	fz = fz * fz * (3 - 2 * fz);
	const l = (a: number, b: number, k: number) => a + (b - a) * k;
	return l(
		l(l(hash(xi, yi, zi), hash(xi + 1, yi, zi), fx), l(hash(xi, yi + 1, zi), hash(xi + 1, yi + 1, zi), fx), fy),
		l(l(hash(xi, yi, zi + 1), hash(xi + 1, yi, zi + 1), fx), l(hash(xi, yi + 1, zi + 1), hash(xi + 1, yi + 1, zi + 1), fx), fy),
		fz,
	);
}

export function fbm(x: number, y: number, z: number) {
	return noise(x, y, z) * 0.55 + noise(x * 2.1, y * 2.1, z * 2.1) * 0.3 + noise(x * 4.3, y * 4.3, z * 4.3) * 0.15;
}

export interface Grid {
	ctx: CanvasRenderingContext2D;
	W: number;
	H: number;
	cw: number;
	ch: number;
	cols: number;
	rows: number;
}

/**
 * Dibuja una curva y(x) con precisión de media fila: `-` y `_` en los tramos suaves,
 * `/` `\` en las pendientes y `|` en los saltos. `y` va en filas (el centro de la fila j es j + 0.5).
 */
export function trace(g: Grid, from: number, to: number, y: (x: number) => number, color: (i: number) => string | null) {
	const { ctx, cw, ch, rows } = g;
	const put = (i: number, j: number, c: string) => j >= 0 && j < rows && ctx.fillText(c, i * cw, j * ch);
	for (let i = from; i < to; i++) {
		const fill = color(i);
		if (!fill) continue;
		let min = Infinity, max = -Infinity;
		for (let s = 0; s <= 4; s++) {
			const v = y(i + s / 4);
			if (v < min) min = v;
			if (v > max) max = v;
		}
		ctx.fillStyle = fill;
		const span = max - min, m = (min + max) / 2, j = Math.floor(m);
		if (span < 0.9) {
			const f = m - j;
			if (f < 0.25) put(i, j - 1, '_');
			else put(i, j, f < 0.75 ? '-' : '_');
		} else if (span < 1.8) put(i, j, y(i + 1) < y(i) ? '/' : '\\');
		else for (let r = Math.floor(min); r <= Math.floor(max - 0.01); r++) put(i, r, '|');
	}
}

interface Scene {
	fontSize: (width: number) => number;
	draw: (g: Grid, t: number) => void;
	fps?: number;
	/** Peso de la fuente (400 por defecto). */
	weight?: number;
	/** Instante que se dibuja, fijo, cuando el usuario pide menos movimiento. */
	stillAt?: number;
}

/** Monta una escena en un canvas. Solo anima mientras el canvas está a la vista. */
export function mount(canvas: HTMLCanvasElement, scene: Scene) {
	const ctx = canvas.getContext('2d', { alpha: false })!;
	const g: Grid = { ctx, W: 0, H: 0, cw: 0, ch: 0, cols: 0, rows: 0 };
	const reduced = matchMedia('(prefers-reduced-motion: reduce)');
	const interval = 1000 / (scene.fps ?? 20);
	const t0 = performance.now();
	let raf = 0, last = 0, visible = false;

	function paint() {
		if (!g.W || !g.H) return;
		ctx.fillStyle = BG;
		ctx.fillRect(0, 0, g.W, g.H);
		scene.draw(g, reduced.matches ? (scene.stillAt ?? 1e3) : (performance.now() - t0) / 1000);
	}

	function resize() {
		const rect = canvas.getBoundingClientRect();
		const dpr = Math.min(window.devicePixelRatio || 1, 2);
		g.W = rect.width;
		g.H = rect.height;
		canvas.width = Math.round(g.W * dpr);
		canvas.height = Math.round(g.H * dpr);
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		const fs = scene.fontSize(g.W);
		ctx.font = `${scene.weight ?? 400} ${fs}px ${FONT}`;
		ctx.textBaseline = 'top';
		g.cw = ctx.measureText('#').width;
		g.ch = Math.round(fs * 1.1);
		g.cols = Math.ceil(g.W / g.cw);
		g.rows = Math.ceil(g.H / g.ch);
		paint();
	}

	function frame(now: number) {
		raf = requestAnimationFrame(frame);
		if (now - last < interval) return;
		last = now;
		paint();
	}

	function sync() {
		cancelAnimationFrame(raf);
		raf = 0;
		if (reduced.matches) paint();
		else if (visible && !document.hidden) raf = requestAnimationFrame(frame);
	}

	new ResizeObserver(resize).observe(canvas);
	new IntersectionObserver(([e]) => {
		visible = e.isIntersecting;
		sync();
	}).observe(canvas);
	document.addEventListener('visibilitychange', sync);
	reduced.addEventListener('change', sync);
	document.fonts?.load(`10px ${FONT}`).then(resize, () => {});
	resize();

	return { paint, reduced };
}
