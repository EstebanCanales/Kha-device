# Landing page

The public page for Kha-device 01. It is an [Astro](https://astro.build) site that builds to static files: no server code, no database. It explains the project and links to the dashboard, which is a different site served by the Django backend.

Live: <https://kha-device.up.railway.app> (English) and <https://kha-device.up.railway.app/es/> (Spanish).

## Commands

Run from this folder. [Bun](https://bun.sh) is the package manager.

| Command | Action |
| --- | --- |
| `bun install` | Install dependencies |
| `bun dev` | Development server at `http://localhost:4321` |
| `bun run build` | Build the site into `dist/` |
| `bun preview` | Serve the built site locally |

`PUBLIC_APP_URL` sets where the "Open the app" links point. It is read **at build time** and defaults to `http://127.0.0.1:8000/app/`.

## Structure

```text
landing/
├── public/                  files served as they are: 3D models, video, poster, icons
└── src/
    ├── pages/               index.astro (English, at /) and es/index.astro (Spanish, at /es/)
    ├── layouts/Layout.astro document shell, fonts, colours, language handling
    ├── i18n/content.ts      every sentence on the page, once per language
    ├── components/          one file per section (see below)
    └── scripts/             shared drawing code
```

## Sections

`components/Page.astro` assembles the page in this order:

| Component | Section | Notes |
| --- | --- | --- |
| `LangSwitch.astro` | EN / ES switch | Remembers the choice in the browser |
| `Hero.astro` | Opening | "Earthrise" (Apollo 8) redrawn in ASCII |
| `Video.astro` | Presentation video | Custom player; browser controls remain if scripts are off |
| `Different.astro` | What makes us different | ASCII Saturn V over the Moon, one screen tall |
| `Iss.astro` | Technology | The International Space Station in ASCII |
| `Devices.astro` | Devices | 3D harness with both devices (three.js) |
| `Flow.astro` | How it works | Six steps; a signal travels down the centre rail |
| `Models.astro` | Artificial intelligence | The three models, each with an ASCII animation |
| `SolarSystem.astro` | Solar system | The Sun and eight planets in ASCII |
| `Footer.astro` | Footer | Logo in ASCII and project links |
| `Launch.astro` | Opening the app | Full-screen journey past the planets when an "Open the app" link is pressed, then the dashboard opens |

## How the pieces work

**Text and languages.** Components contain no sentences of their own; they read from `src/i18n/content.ts`. English is the main language and lives at `/`; Spanish lives at `/es/`. To add a language, copy the `en` block, translate it, and register it in `content` and `LANGS`. The page does not switch language by itself; it follows what the visitor chose in the switch.

**ASCII scenes.** `src/scripts/ascii.ts` provides `mount()`, which sizes a canvas to a grid of characters and calls a `draw` function for each frame. A scene decides, cell by cell, which character and colour to paint. Scenes animate only while they are on screen. When the visitor's system asks for reduced motion, each scene paints one still frame.

**3D harness.** `src/scripts/harness-scene.ts` builds the straps and hardware in code and loads the two device models from `public/Dosimeter.glb` and `public/vitales.glb`. As the visitor scrolls, the harness assembles and the camera moves to the device being read about. It can be dragged to rotate.

**Reveal on scroll.** `src/scripts/reveal.ts` fades in elements marked `data-reveal` as they enter the window.

**Video.** `public/kha-device.mp4` is a 1080p copy made for the web, with `kha-device-poster.jpg` as its first frame. The 4K original is kept out of the repository because of its size.

## Conventions

- Scoped styles in each component; colours and fonts come from variables in `Layout.astro`.
- Layouts must work at phone width and never cause horizontal scrolling.
- Decorative canvases carry `aria-hidden` or a text label; controls have accessible names.
- Simulated data shown on the page is labelled as simulated.

## Deployment

The site is deployed to Railway from this folder:

```bash
railway up landing --path-as-root --service landing --environment production --ci -m "<summary>"
```

Run it from the repository root. See [../docs/deploy-railway.md](../docs/deploy-railway.md).
