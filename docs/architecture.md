# How Kha-device 01 works

This document explains every part of the project in plain terms: what it does, where the code lives, and why it is built that way. Read it top to bottom once; after that, use the headings to find a part.

Everything described here runs on **simulated data**. Where a number is a simulation choice or a provisional engineering choice, the text says so.

## The idea in one paragraph

An astronaut wears a harness with two devices. One reads vital signs. The other measures ionizing radiation. Both send their readings to a backend, which stores them exactly as received. A person then opens a dashboard that compares the latest readings with that same astronaut's earlier readings, and shows what changed. Three short texts summarise it: one about health, one about the space environment, and one that joins both.

## The parts

| Part | Where | Runs as |
| --- | --- | --- |
| Backend | `config/`, `monitoring/`, `ia/` | One Django process (a "modular monolith": one deployable, separate modules inside) |
| Database | PostgreSQL in the hosted deployment, SQLite on a laptop | Managed service or a local file |
| Dashboard | `monitoring/templates/monitoring/app.html` | A page served by the backend |
| Landing page | `landing/` | A separate static site |
| Simulators | `scripts/`, `monitoring/demo_data.py` | Command-line programs |

The landing page and the backend are two sites. The landing page links to the dashboard; signing out of the dashboard returns to the landing page.

## The data model

The model answers one question: *who measured what, with which instrument, when, and under which conditions?* The classes are in `monitoring/models/`.

| Record | What it represents |
| --- | --- |
| `Participant` | The person, known only by a pseudonym. No names are stored |
| `MonitoringSession` | A period of monitoring for one participant. It also lists which accounts may read it |
| `Device` | A physical unit (or a simulated one). Its `source` says which: `simulated` or `hardware` |
| `DeviceCredential` | A secret a device uses to send data. Stored only as a hash; revocable one by one |
| `Sensor` | One measuring element inside a device, for example one dosimeter chamber |
| `SensorCapability` | A metric and unit a sensor is allowed to report. Nothing is enabled automatically |
| `SessionDevice` | "This device was assigned to this session from this time to that time" |
| `CounterEpoch` | One life of a cumulative counter, from a reset to the next. Readings from different epochs are never added together |
| `TelemetryPacket` | One message from a device: all its readings share one capture time |
| `Measurement` | One reading: sensor, metric, value, unit, quality |
| `ECGSample`, `AnalysisResult` | Tables reserved for raw ECG and stored analysis results. Nothing writes to them yet |

Three rules shape the whole model:

- **Two times per reading.** `observed_at` is when the instrument captured it; `received_at` is when the server got it. A reading that arrives late keeps its original time. The server never replaces one with the other.
- **Missing is not zero.** A reading has a quality: `valid`, `unreliable` or `missing`. A missing reading has no value at all, so a disconnected sensor can never look like a heart rate of zero.
- **Simulated and real never mix.** Every device has a provenance, and every query that returns readings must say which one it wants.

Primary keys are random UUIDs. Devices, sessions and sensors also have readable identifiers (`cad-sim-001`, `session-kha-001`), which are what devices put in their messages. More detail: [models.md](models.md).

## Ingestion: how a reading gets in

The route is `POST /api/v1/telemetry/batches/`. The code is in `monitoring/services.py`, `monitoring/serializers.py` and `monitoring/authentication.py`.

1. **The device identifies itself** with `Authorization: Device <credential-id>:<secret>`. A device credential allows ingestion and nothing else; it cannot read data or open the dashboard.
2. **The batch is checked for shape:** 1 to 100 packets, each with 1 to 32 readings, at most 262,144 bytes.
3. **Each packet is checked for meaning.** The credential must belong to the device named in the packet. The device must be assigned to the session at the time of capture. Each sensor must belong to the device and be allowed to report that metric in that unit. Values must be finite decimal numbers sent as text, so no precision is lost.
4. **The whole batch is stored or none of it.** If one new packet is invalid, nothing from that request is kept.
5. **The device gets one status per packet:** `inserted` or `duplicate`.

**Retries are safe.** A device chooses a `packet_id` before the first attempt and keeps it when it retries. The database enforces that a device cannot have two packets with the same id. If the retry is identical, the server answers "duplicate" and stores nothing new. If the same id arrives with different content, the server answers `409 Conflict`, because that is a bug in the sender, not a retry.

**Why the device does not say who the participant is.** The server works that out from the session and the assignment. A device that could name a participant could write into someone else's history.

No medical limits are applied at this stage. Ingestion checks that a reading is well formed and allowed, not that it is healthy. The full contract, with every error code, is [telemetry-contract.md](telemetry-contract.md).

## Queries: how a reading gets out

All read routes hang from a session: `/api/v1/sessions/{uuid}/...`. The code is in `monitoring/views.py`.

- `measurements/` is the full history, paginated, in a stable order.
- `latest/` is the most recent reading per sensor, metric, unit and counter epoch.
- `overview/` is what the dashboard uses: analysis, chart series and the active summary engine in one response.
- `analysis/`, `summary/`, `report/` and `radiation-context/` are described below.

**Who may read** is decided in one place, `monitoring/access.py`, so every route agrees:

1. Staff read everything.
2. With `OPEN_READ_ACCESS` on, every signed-in account reads everything. This is for demonstrations with simulated data.
3. Otherwise an account reads only the sessions it was authorized for.

4. With `PUBLIC_DEMO` on, a visitor without an account is a reader too, limited to simulated data: a request for hardware data answers `403`.

A session an account may not read answers `404`, the same as a session that does not exist, so the API does not reveal which sessions exist. Changing anything is staff-only in every mode.

## Analysis: what changed

The code is `monitoring/analysis.py`. It runs when asked and stores nothing.

For heart rate, SpO₂, respiratory rate and skin temperature:

1. Take the session's readings in time order. At least 20 are needed.
2. The first 40% (at least 10 readings) are the **baseline**: how this person was at the start.
3. The last 10 readings are the **recent** window.
4. Compare the two with the median and the median absolute deviation, which are not thrown off by one odd reading.
5. If the recent median is 3 or more deviations from the baseline, report a shift up or down.

For each dosimeter chamber it reports the latest cumulative dose and compares the recent rate of increase with the early rate; 3 times the early rate or more is reported as a faster accumulation. It also lists missing readings and long pauses in the timeline.

**What this is not.** The comparison is with the person's own start of session, not with a textbook normal range. The numbers 3, 10, 20 and 40% are provisional engineering choices. A reported shift means "this moved clearly away from where it started", not "this is a medical problem".

The dashboard charts show the last 24 hours, with at most 120 points per series.

## The summary module

The code is in `ia/`. It takes the analysis and produces three texts through three steps:

1. **Health specialist:** the vital signs.
2. **Space specialist:** the dosimeter and, when available, NASA space-weather events.
3. **Synthesis:** joins both into findings, uncertainties and missing data.

`IA_ENGINE` selects how the texts are written:

| Engine | How | When to use it |
| --- | --- | --- |
| `rules` | Fixed sentence templates, no language model | Default. Deterministic, instant, and what the hosted site runs |
| `ollama` | Three language models served by a local Ollama | On a machine with the models installed |
| `huggingface` | The same models through the transformers library | Optional; not validated with the real weights |

**The design does not trust the model's text.** Language models of this size invent figures and offer causes nobody asked for. So:

- The findings, the flagged changes and the missing-data list always come from the analysis, computed from the readings. They survive even if the model returns nonsense.
- What a model writes is shown apart, labelled as possibly wrong.
- A sentence that cites a figure that is not in the readings, or describes a change between two identical figures, is discarded.

`python -m ia.evaluation` compares model combinations on fixed cases. More detail, including what was observed when the models ran: [../ia/README.md](../ia/README.md).

## NASA space-weather context

`monitoring/nasa_radiation.py` asks NASA's DONKI service for radiation-belt enhancement events in a date range. `monitoring/space_context.py` turns that into a short context for the week before the last reading.

These are **events in the space environment, not readings from the worn dosimeter.** They are kept separate from telemetry, never converted into a dose, and never used to estimate risk. If NASA does not answer, or no key is configured, the dashboard says so and everything else works the same.

## The dashboard

`/app/` is one HTML page with its own script and no build step. It talks only to `/api/v1/`.

- It asks for `overview` every 15 seconds while it is not paused and the tab is visible.
- **Pause** stops the requests; **resume** asks again at once.
- Changing the source (simulated or hardware) or the session reloads the data.
- **Update** in the analysis panel runs the summary module.
- With no readable session it explains that instead of requesting anything.

Network and server errors are explained on screen, the last data stays visible, and a retry is offered.

## Accounts

People use Django accounts. The sign-up code is `monitoring/signup.py`.

- `/accounts/signup/` creates a non-staff account and signs it in. It can be switched off with `ALLOW_SIGNUP`.
- Passwords go through Django's validators.
- Attempts are limited per client address.
- If `SIGNUP_DEMO_SESSION` names a session, new accounts are authorized for it, and so are existing accounts the next time they sign in.

The login and sign-up pages share one template and an animated ASCII background (`monitoring/static/monitoring/ascii-bg.js`) that only draws; it reads and sends nothing.

## The simulators

Because there is no hardware, the data comes from programs. All of them mark their data as `simulated`.

| Program | What it does |
| --- | --- |
| `manage.py demo_kha` | One command: migrate, register both devices, load a day of data. Writes through the same ingestion code, without HTTP |
| `scripts/simulate_kha.py` | The same data, sent over the real HTTP endpoint with device credentials |
| `scripts/simulate_telemetry.py` | Exercises duplicates, delays, missing readings and counter resets |
| `scripts/vital_signs.py`, `scripts/dosimeter.py` | Earlier single-device simulators with their own guides |

`monitoring/demo_data.py` generates the Kha-device 01 readings: one sample every 30 minutes. In the `stress` scenario the last 30% of the window shifts (higher heart rate, lower SpO₂, faster breathing, warmer skin, faster dose accumulation) so the analysis has something to find. Respiratory rate is a synthetic derived channel; no raw optical or ECG signal is processed.

## The landing page

`landing/` is an Astro site that builds to static files. It has no backend of its own. Sections, in order:

| Section | Component | What it shows |
| --- | --- | --- |
| Hero | `Hero.astro` | "Earthrise" redrawn in ASCII, and the link to the dashboard |
| Video | `Video.astro` | The presentation video in a custom player |
| What makes us different | `Different.astro` | The project's pitch beside an ASCII Saturn V over the Moon |
| Technology | `Iss.astro` | The International Space Station in ASCII |
| Devices | `Devices.astro` | A 3D harness with both devices; the camera follows the text |
| How it works | `Flow.astro` | Six steps from sensors to summary, with a signal that travels down the page |
| Artificial intelligence | `Models.astro` | The three models |
| Solar system | `SolarSystem.astro` | The Sun and planets in ASCII |

All text lives in `landing/src/i18n/content.ts`, once per language. English is served at `/` and Spanish at `/es/`. More detail: [../landing/README.md](../landing/README.md).

## Hosting

Three services on Railway: the backend, PostgreSQL, and the landing page. Before each release the backend applies database migrations; at start it collects its static files and runs gunicorn. The database is reachable only from inside the project's private network. See [deploy-railway.md](deploy-railway.md).

## Safety boundaries

These hold everywhere in the project:

- No diagnosis, medical alert, treatment recommendation or radiological-risk calculation.
- Original quantities and units are stored as received; nothing is converted.
- Missing or unreliable readings never become zero.
- Simulated provenance is always explicit.
- Device credentials are individual and revocable; there is no shared device token.
- Tokens, secrets, names and complete physiological payloads must not be written to logs.

## Where to change things

| To change | Look at |
| --- | --- |
| What a device may send | `monitoring/models/shared.py` (metrics and units), then a `SensorCapability` |
| Validation of incoming data | `monitoring/serializers.py`, `monitoring/services.py` |
| Who may read a session | `monitoring/access.py` |
| Analysis thresholds | The constants at the top of `monitoring/analysis.py` |
| Summary wording | `ia/inputs.py`, `ia/backends.py` |
| Simulated data rate or shape | `monitoring/demo_data.py` |
| Dashboard | `monitoring/templates/monitoring/app.html` |
| Landing text | `landing/src/i18n/content.ts` |
| Deployment settings | `config/settings.py`, [deploy-railway.md](deploy-railway.md) |
