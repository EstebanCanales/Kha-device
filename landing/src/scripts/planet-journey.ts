// @ts-nocheck
/* Viaje por el sistema solar en ASCII: cada planeta aparece lejos, se acerca y pasa de largo, de Mercurio a Neptuno.
 * Es la misma animación de las pantallas de acceso del backend (monitoring/static/monitoring/ascii-bg.js),
 * aquí como función: la landing la muestra al abrir la app. Solo dibuja: no lee ni envía datos. */

/**
 * Dibuja el viaje en `canvas` hasta que se llame a la función devuelta.
 * `speed` acelera el paso de los planetas; `caption`, si se da, recibe el nombre del planeta más cercano,
 * traducido con `names` (de nombre en español a nombre en el idioma de la página) cuando se proporciona.
 */
export function startJourney(canvas, caption = null, speed = 1, names = null) {
	const t0 = performance.now();
	const ctx = canvas.getContext('2d');
	const calm = matchMedia('(prefers-reduced-motion: reduce)');
	const RAMP = ' .,:;-=+*#%@';
	// Misma paleta de estrellas que el sistema solar de la landing.
	const STAR_COLORS = [[129, 150, 210], [214, 201, 136], [214, 140, 120], [136, 204, 194]];
	const TAU = Math.PI * 2;

	const mix = (a, b, k) => a + (b - a) * k;
	const mix3 = (a, b, k) => [mix(a[0], b[0], k), mix(a[1], b[1], k), mix(a[2], b[2], k)];
	const clamp01 = (x) => Math.max(0, Math.min(1, x));
	const smooth = (a, b, x) => { const k = clamp01((x - a) / (b - a)); return k * k * (3 - 2 * k); };
	const hash = (a, b) => { const h = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return h - Math.floor(h); };
	const noise = (x, y) => {
		const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
		const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
		const a = hash(xi, yi), b = hash(xi + 1, yi), c = hash(xi, yi + 1), d = hash(xi + 1, yi + 1);
		return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
	};
	// Distancia al cráter más cercano (celdas de Worley), en radios de ese cráter.
	const crater = (x, y) => {
		const xi = Math.floor(x), yi = Math.floor(y);
		let best = 9;
		for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
			const cx = xi + i + hash(xi + i, yi + j), cy = yi + j + hash(yi + j + 7, xi + i + 3);
			const r = 0.18 + 0.22 * hash(xi + i + 5, yi + j + 9);
			best = Math.min(best, Math.hypot(x - cx, y - cy) / r);
		}
		return best;
	};

	/* ---------- los ocho planetas: cada textura devuelve [brillo 0-1, color] ---------- */

	// Ruido de tres escalas (0 a 1): relieve grande con grano fino encima.
	const fbm = (x, y) => (noise(x, y) + noise(x * 2.1 + 5, y * 2.1 + 9) * 0.5 + noise(x * 4.3 + 13, y * 4.3 + 2) * 0.25) / 1.75;
	// Diferencia de longitud envuelta a [-PI, PI]: para colocar manchas que giran con el planeta.
	const wrap = (d) => ((d % TAU) + TAU + Math.PI) % TAU - Math.PI;
	const oval = (lon, lat, at, y, w, h) => 1 - Math.hypot(wrap(lon - at) / w, (lat - y) / h);

	// Cada textura devuelve [detalle 0-1, color]. `hue` es el tono del planeta en el sistema solar de la landing
	// y `air` el de su atmósfera.
	const PLANETS = [
		{ name: 'Mercurio', hue: [196, 190, 182], air: [210, 200, 190], size: 0.7, tex(lon, lat) {
			// Cráteres de dos tamaños sobre un suelo moteado.
			const big = crater(lon * 3.2, lat * 4), small = crater(lon * 8 + 3, lat * 9 + 1);
			const rim = Math.max(big > 0.8 && big < 1.12 ? 1 - Math.abs(big - 0.96) * 6 : 0, small > 0.75 && small < 1.15 ? 0.6 - Math.abs(small - 0.95) * 3 : 0);
			const pit = big < 0.8 ? 0.45 * (1 - big) : small < 0.75 ? 0.25 * (1 - small) : 0;
			const soil = fbm(lon * 3, lat * 3);
			return [clamp01(0.5 + soil * 0.3 + rim * 0.45 - pit), mix3(mix3([176, 164, 152], [112, 104, 100], soil), [240, 232, 216], Math.max(0, rim) * 0.5)];
		} },
		{ name: 'Venus', hue: [246, 208, 126], air: [255, 226, 150], size: 0.92, tex(lon, lat, lit, spin) {
			// Nubes en chevrones: bandas que se curvan hacia el ecuador y se retuercen.
			const warp = fbm(lon * 1.5 + spin * 0.6, lat * 2) * 2.4;
			const swirl = Math.sin(lat * 6 - Math.abs(lat) * 2 + warp * 2.2 + lon * 1.2) * 0.5 + 0.5;
			const fine = fbm(lon * 5 + warp, lat * 7);
			return [clamp01(0.35 + swirl * 0.4 + fine * 0.3), mix3(mix3([206, 146, 70], [255, 236, 176], swirl), [255, 250, 220], fine * 0.25)];
		} },
		{ name: 'Tierra', hue: [64, 150, 255], air: [110, 200, 255], size: 0.95, tex(lon, lat, lit, spin) {
			const h = fbm(lon * 2 + 8, lat * 2.4 + 3);
			const isLand = h > 0.52, coast = smooth(0.46, 0.52, h);
			const clouds = smooth(0.56, 0.72, fbm(lon * 2.6 - spin * 2 + 20, lat * 3.6));
			let rgb, d;
			if (isLand) {
				// Selva cerca del ecuador, desierto en las franjas secas, montaña donde el terreno sube.
				const dry = smooth(0.25, 0.6, Math.abs(Math.abs(lat) - 0.45) < 0.22 ? 1 - Math.abs(Math.abs(lat) - 0.45) / 0.22 : 0) * noise(lon * 3 + 50, lat * 3);
				rgb = mix3(mix3([36, 170, 92], [226, 178, 96], dry), [150, 140, 128], smooth(0.66, 0.8, h));
				d = 0.55 + (h - 0.52) * 1.4;
			} else {
				rgb = mix3([14, 52, 190], [46, 170, 236], coast); // aguas someras junto a la costa
				d = 0.3 + coast * 0.25;
			}
			if (Math.abs(lat) > 1.1 - fbm(lon * 3, 7) * 0.12) { rgb = [236, 246, 255]; d = 0.9; }
			return [clamp01(mix(d, 0.95, clouds * 0.8)), mix3(rgb, [250, 252, 255], clouds * 0.85)];
		} },
		{ name: 'Marte', hue: [246, 98, 54], air: [255, 170, 130], size: 0.78, tex(lon, lat) {
			const h = fbm(lon * 2.4, lat * 2.6);
			const dark = smooth(0.5, 0.64, fbm(lon * 1.6 + 30, lat * 2.2 + 4)); // regiones oscuras de basalto
			// Valles Marineris: un tajo largo cerca del ecuador.
			const canyon = Math.max(0, oval(lon, lat + fbm(lon * 4, 1) * 0.08, 0.8, -0.12, 0.9, 0.06));
			const craters = crater(lon * 6, lat * 7);
			const rim = craters > 0.8 && craters < 1.1 ? 0.3 : 0;
			let rgb = mix3(mix3([226, 112, 60], [176, 70, 42], h), [96, 44, 36], dark * 0.75);
			rgb = mix3(rgb, [60, 24, 22], Math.min(1, canyon * 3));
			let d = 0.45 + h * 0.4 - dark * 0.2 - canyon * 0.5 + rim;
			if (Math.abs(lat) > 1.2 - fbm(lon * 4, 3) * 0.1) { rgb = [246, 240, 232]; d = 0.95; }
			return [clamp01(d), rgb];
		} },
		{ name: 'Júpiter', hue: [240, 176, 112], air: [250, 214, 170], size: 1.25, tex(lon, lat, lit, spin) {
			// Cinturones y zonas con bordes turbulentos; el ruido arrastra las bandas a lo largo de la longitud.
			const turb = fbm(lon * 3 + spin * 0.4, lat * 9);
			const belt = Math.sin(lat * 11 + turb * 2.4) * 0.5 + 0.5;
			const zone = Math.sin(lat * 4.2 + 0.6) * 0.5 + 0.5;
			let rgb = mix3(mix3([244, 222, 186], [186, 116, 78], belt), [150, 88, 66], (1 - zone) * belt * 0.6);
			let d = 0.35 + belt * 0.35 + turb * 0.3;
			const spot = oval(lon, lat, 1.1, -0.36, 0.34, 0.15); // Gran Mancha Roja
			if (spot > 0) { rgb = mix3(rgb, [206, 62, 44], Math.min(1, spot * 2.2)); d = mix(d, 0.85 - spot * 0.3, Math.min(1, spot * 2)); }
			for (const at of [2.6, 4.1, 5.3]) { // óvalos blancos del hemisferio sur
				const o = oval(lon, lat, at, -0.58, 0.12, 0.06);
				if (o > 0) { rgb = mix3(rgb, [252, 246, 232], Math.min(1, o * 2.5)); d = Math.max(d, 0.9 * Math.min(1, o * 2.5)); }
			}
			return [clamp01(d), rgb];
		} },
		{ name: 'Saturno', hue: [248, 216, 136], air: [250, 232, 180], size: 1.05, rings: true, tex(lon, lat, lit, spin) {
			const turb = fbm(lon * 2 + spin * 0.3, lat * 7);
			const band = Math.sin(lat * 9 + turb * 1.2) * 0.5 + 0.5;
			let rgb = mix3([246, 226, 172], [196, 160, 108], band);
			let d = 0.45 + band * 0.3 + turb * 0.2;
			// Sombra de los anillos sobre el planeta: una franja oscura bajo el ecuador.
			const shadow = smooth(0.02, 0.07, -lat) * (1 - smooth(0.16, 0.22, -lat));
			rgb = mix3(rgb, [74, 58, 44], shadow * 0.7); d -= shadow * 0.3;
			if (lat > 1.05) { rgb = mix3(rgb, [150, 170, 190], 0.5); } // casquete polar azulado
			return [clamp01(d), rgb];
		} },
		{ name: 'Urano', hue: [120, 238, 240], air: [170, 245, 245], size: 0.98, tex(lon, lat) {
			const band = Math.sin(lat * 7 + fbm(lon * 1.5, lat * 3) * 0.8) * 0.5 + 0.5;
			const haze = smooth(0.7, 1.3, lat); // el polo iluminado es más claro
			return [clamp01(0.45 + band * 0.2 + haze * 0.3 + fbm(lon * 4, lat * 6) * 0.15), mix3(mix3([158, 236, 238], [104, 196, 222], band), [226, 250, 250], haze * 0.6)];
		} },
		{ name: 'Neptuno', hue: [84, 122, 255], air: [120, 160, 255], size: 0.96, tex(lon, lat, lit, spin) {
			const band = Math.sin(lat * 8 + fbm(lon * 2 + spin * 0.5, lat * 5) * 1.6) * 0.5 + 0.5;
			let rgb = mix3([30, 58, 206], [84, 136, 246], band);
			let d = 0.35 + band * 0.35;
			const spot = oval(lon, lat, 2.2, -0.3, 0.3, 0.14); // Gran Mancha Oscura
			if (spot > 0) { rgb = mix3(rgb, [14, 24, 110], Math.min(1, spot * 2.4)); d -= Math.min(0.3, spot * 0.6); }
			const cirrus = smooth(0.72, 0.84, noise(lon * 5 - spin * 2, lat * 14)); // cirros blancos y estirados
			return [clamp01(mix(d, 0.95, cirrus)), mix3(rgb, [240, 246, 255], cirrus * 0.9)];
		} },
	];

	/* ---------- viaje ---------- */

	const PERIOD = 7;      // segundos entre un planeta y el siguiente
	const LIFE = 1.8;      // cada planeta vive 1.8 periodos: se cruza con el que viene detrás
	const LIGHT = [-0.55, 0.45, 0.7];
	const RING_TILT = 0.36;
	// Estrellas que salen del punto de fuga, como al avanzar; cada una repite su recorrido a su ritmo.
	const stars = Array.from({ length: 40 }, (_, i) => ({ a: hash(i, 1.3) * TAU, off: hash(i, 2.9), rate: 0.035 + hash(i, 4.1) * 0.05, rgb: STAR_COLORS[Math.floor(hash(i, 5.5) * STAR_COLORS.length)] }));

	let W = 0, H = 0, cw = 8, ch = 14, cols = 0, rows = 0;
	function size() {
		const dpr = Math.min(2, devicePixelRatio || 1);
		W = innerWidth; H = innerHeight;
		canvas.width = W * dpr; canvas.height = H * dpr;
		canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
		const fs = W < 700 ? 8 : 10; // letra pequeña: más celdas, más detalle
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		ctx.font = `500 ${fs}px ui-monospace, "SF Mono", Menlo, monospace`;
		ctx.textBaseline = 'top';
		cw = ctx.measureText('M').width; ch = fs * 1.15;
		cols = Math.ceil(W / cw); rows = Math.ceil(H / ch);
	}

	const styles = new Map();
	const paint = (rgb) => {
		// 32 niveles por canal: degradados limpios sin crear miles de estilos distintos.
		const r = rgb[0] >> 3, g = rgb[1] >> 3, b = rgb[2] >> 3, key = (r << 10) | (g << 5) | b;
		let s = styles.get(key);
		if (!s) { s = `rgb(${r * 8 + 4},${g * 8 + 4},${b * 8 + 4})`; styles.set(key, s); }
		return s;
	};
	/** Dónde está y cuánto mide el planeta número k cuando el viaje va por `beat` (tiempo en periodos). */
	function pose(k, beat) {
		const age = beat - k;
		if (age < 0 || age >= LIFE) return null;
		const planet = PLANETS[((k % PLANETS.length) + PLANETS.length) % PLANETS.length];
		const wide = W > 900;
		const far = H * 0.03, near = H * 0.6;
		// Crece de forma exponencial: así se percibe un acercamiento a velocidad constante.
		const R = far * Math.pow(near / far, age / LIFE) * planet.size;
		// Sale del punto de fuga y se aparta hacia un lado al pasar; el lado alterna de un planeta a otro.
		const dir = hash(k, 7.7) * 0.9 - 0.45 + (k % 2 ? Math.PI : 0);
		const drift = (R - far) * 1.5;
		const vx = (wide ? W * 0.7 : W * 0.5) + Math.sin(beat * 0.9) * W * 0.012, vy = H * 0.46 + Math.cos(beat * 0.7) * H * 0.015;
		return {
			planet, R, age,
			cx: vx + Math.cos(dir) * drift * (wide ? 1 : 0.7), cy: vy + Math.sin(dir) * drift * 0.8 + drift * 0.25,
			fade: smooth(0.08, 0.62, age) * (1 - smooth(LIFE - 0.8, LIFE - 0.04, age)),
			spin: beat * 0.35 + k,
		};
	}

	/** Qué carácter y color pone un planeta en el punto (x, y) de la pantalla; null si no lo toca. */
	function sample(p, x, y, i, j, tick) {
		const dx = (x - p.cx) / p.R, dy = (y - p.cy) / p.R, r2 = dx * dx + dy * dy;
		if (p.planet.rings) {
			const rho = Math.hypot(dx, dy / Math.sin(RING_TILT));
			// El anillo pasa por delante del planeta en su mitad inferior y por detrás en la superior.
			if (rho > 1.28 && rho < 2.32 && (r2 >= 1 || dy > 0)) {
				// Anillo C tenue, B brillante, división de Cassini, anillo A con la división de Encke.
				const gap = (rho > 1.86 && rho < 1.96) || (rho > 2.18 && rho < 2.21);
				if (!gap) {
					const base = rho < 1.5 ? 0.42 : rho < 1.86 ? 1 : 0.74;
					const lanes = 0.72 + 0.28 * noise(rho * 46, 3); // anillas finas
					// La parte del anillo que pasa por detrás queda en la sombra del planeta, a la derecha.
					const shade = dy < 0 && dx > 0 && Math.abs(dy) < 0.9 * Math.sin(RING_TILT) * 1.2 && r2 < 2.6 ? 0.55 : 1;
					const lum = base * lanes * shade;
					const ink = [236, 214, 160].map((v) => v * lum);
					return [lum > 0.8 ? '=' : lum > 0.5 ? '-' : '.', ink, ink.map((v) => v * 0.34), p.fade];
				}
			}
		}
		if (r2 < 1) {
			const nz = Math.sqrt(1 - r2), nx = dx, ny = -dy;
			// Misma luz que el sistema solar de la landing: suave, con la cara de noche todavía visible, y cada planeta
			// en su tono propio. La textura (cráteres, bandas, continentes) solo matiza ese tono.
			const lit = clamp01(nx * LIGHT[0] * 1.1 + ny * LIGHT[1] * 1.1 + nz * 0.42);
			const [detail, texture] = p.planet.tex(Math.atan2(nx, nz) + p.spin, Math.asin(ny), 1, p.spin);
			const k = (0.5 + lit * 0.62) * (0.62 + 0.42 * detail);
			const tone = mix3(texture, p.planet.hue, 0.24);
			const c = RAMP[Math.min(RAMP.length - 2, Math.max(1, Math.floor((0.2 + lit * 0.42 + detail * 0.36) * (RAMP.length - 1))))];
			// Relleno de la celda en el mismo tono, a media luz: el planeta se ve lleno de color.
			return [c, tone.map((v) => Math.min(255, v * k)), tone.map((v) => v * k * 0.5), p.fade];
		}
		if (r2 < 1.14 && p.R > 26) {
			// Halo: más denso junto al disco y solo del lado que da al Sol.
			const edge = 1 - (r2 - 1) / 0.14;
			const sunward = clamp01((dx * LIGHT[0] - dy * LIGHT[1]) * 0.9 + 0.55);
			if (hash(i, j + tick) < edge * edge * 0.8 * sunward * p.fade) return [edge > 0.6 ? ':' : '.', (p.planet.air ?? [150, 190, 255]).map((v) => v * (0.45 + 0.4 * edge) * p.fade)];
		}
		return null;
	}

	function frame(now) {
		const beat = ((now - t0) / 1000 / PERIOD) * speed;
		const newest = Math.floor(beat);
		// Primero el más viejo (el más cercano): tapa al que viene detrás.
		const active = [pose(newest - 1, beat), pose(newest, beat)].filter(Boolean);
		if (caption && active.length) {
			const lead = active.reduce((a, b) => (Math.abs(a.age - 0.95) < Math.abs(b.age - 0.95) ? a : b));
			if (caption.dataset.name !== lead.planet.name) {
				caption.dataset.name = lead.planet.name;
				caption.classList.add('is-out');
				caption.textContent = names?.[lead.planet.name] ?? lead.planet.name; // nombre en el idioma de la página
				caption.classList.remove('is-out');
			}
		}

		ctx.clearRect(0, 0, W, H);
		const vx = W > 900 ? W * 0.7 : W * 0.5, vy = H * 0.46, reach = Math.hypot(W, H) * 0.75;
		for (const s of stars) {
			const f = (s.off + (now / 1000) * s.rate) % 1;
			const dist = 24 + reach * f * f;
			const px = vx + Math.cos(s.a) * dist, py = vy + Math.sin(s.a) * dist * 0.8;
			if (px < 0 || px > W || py < 0 || py > H) continue;
			const glow = smooth(0, 0.2, f) * (1 - smooth(0.82, 1, f)) * (0.75 + 0.25 * Math.sin(now / 600 + s.a * 9));
			ctx.fillStyle = paint(s.rgb.map((v) => v * glow));
			ctx.fillText(f > 0.6 ? '*' : f > 0.3 ? '+' : '.', px, py);
			if (f > 0.45) { // una estela corta, hacia el punto de fuga
				ctx.fillStyle = paint(s.rgb.map((v) => v * glow * 0.4));
				ctx.fillText('.', px - Math.cos(s.a) * cw * 1.8, py - Math.sin(s.a) * ch * 1.2);
			}
		}

		// Solo se recorren las celdas que algún planeta (o su anillo) puede tocar.
		let x0 = cols, x1 = 0, y0 = rows, y1 = 0;
		for (const p of active) {
			const span = p.R * (p.planet.rings ? 2.35 : 1.12);
			x0 = Math.min(x0, Math.floor((p.cx - span) / cw)); x1 = Math.max(x1, Math.ceil((p.cx + span) / cw));
			y0 = Math.min(y0, Math.floor((p.cy - span) / ch)); y1 = Math.max(y1, Math.ceil((p.cy + span) / ch));
		}
		const tick = Math.floor(now / 420);
		let last = '';
		for (let j = Math.max(0, y0); j < Math.min(rows, y1); j++) {
			for (let i = Math.max(0, x0); i < Math.min(cols, x1); i++) {
				const x = i * cw + cw / 2, y = j * ch + ch / 2;
				let hit = null;
				for (const p of active) { hit = sample(p, x, y, i, j, tick); if (hit) break; }
				if (!hit || hit[0] === ' ') continue;
				// El planeta entero aparece y se va por transparencia: sin huecos ni parpadeos.
				ctx.globalAlpha = hit[3] ?? 1;
				if (hit[2]) { ctx.fillStyle = paint(hit[2]); last = ''; ctx.fillRect(i * cw, j * ch, cw + 0.5, ch + 0.5); }
				const style = paint(hit[1]);
				if (style !== last) { ctx.fillStyle = style; last = style; }
				ctx.fillText(hit[0], i * cw, j * ch);
			}
		}
		ctx.globalAlpha = 1;
	}

	let raf = 0;
	const loop = (now) => { frame(now); raf = requestAnimationFrame(loop); };
	const resize = () => size();
	size();
	addEventListener('resize', resize);
	raf = requestAnimationFrame(loop);
	return () => { cancelAnimationFrame(raf); removeEventListener('resize', resize); };
}
