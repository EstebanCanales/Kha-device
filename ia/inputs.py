"""Turn a `monitoring.analysis` result into the text facts each specialist receives."""

from .contracts import Fact, SpecialistInput

HEALTH_LABELS = {
    "heart_rate": "Frecuencia cardíaca",
    "spo2": "Saturación de oxígeno (SpO₂)",
    "respiratory_rate": "Frecuencia respiratoria",
    "skin_temperature": "Temperatura cutánea",
}
CHAMBER_LABELS = {"dis_high": "cámara DIS de alta resolución", "dis_low": "cámara DIS de baja resolución"}
SHIFT_WORDS = {"shift_up": "subió", "shift_down": "bajó"}
UNITS = {"degC": "°C", "breaths/min": "resp/min", "bpm": "lpm"}
GRAVITY = {"earth": "Tierra", "microgravity": "microgravedad", "partial": "gravedad parcial", "hypergravity": "hipergravedad"}


def unit(value: str) -> str:
    return UNITS.get(value, value)


def describe_missing(analysis: dict) -> list[str]:
    """Spanish sentences for the structured `missing_data` items of an analysis."""
    labels = {**HEALTH_LABELS, "absorbed_dose_cumulative": "Dosis absorbida acumulada"}
    out = []
    for item in analysis["missing_data"]:
        label, count = labels.get(item.get("metric"), item.get("metric")), item.get("count", 0)
        match item["code"]:
            case "no_valid_readings":
                out.append(f"{label}: sin lecturas válidas.")
            case "no_dose_readings":
                out.append("Dosis acumulada: sin lecturas del dosímetro.")
            case "missing_readings":
                out.append(f"{label}: {count} lectura(s) ausente(s) por señal perdida.")
            case "unreliable_readings":
                out.append(f"{label}: {count} lectura(s) poco fiables.")
            case "timeline_gaps":
                out.append(f"{count} pausa(s) en la telemetría.")
    return out


def build_health_input(analysis: dict) -> SpecialistInput:
    facts = []
    for metric, label in HEALTH_LABELS.items():
        result = analysis["metrics"].get(metric, {})
        status = result.get("status", "no_data")
        if status in ("stable", "shift_up", "shift_down"):
            base, recent, u = result["baseline"]["median"], result["recent"]["median"], unit(result["unit"])
            if status == "stable":
                text = f"{label}: estable respecto a su línea base ({base} → {recent} {u})."
            else:
                text = (
                    f"{label}: {SHIFT_WORDS[status]} respecto a su línea base ({base} → {recent} {u}), "
                    f"un cambio de {abs(result['z_score'])} veces la dispersión habitual."
                )
            facts.append(Fact(metric, text, "" if status == "stable" else status))
        elif status == "insufficient_data":
            facts.append(Fact(metric, f"{label}: solo {result['readings']} lecturas válidas; no alcanzan para fijar una línea base.", "insufficient"))
        else:
            facts.append(Fact(metric, f"{label}: sin lecturas válidas.", "no_data"))
    # Changes first, so a truncated prompt never drops them.
    facts.sort(key=lambda f: f.flag in ("", "insufficient", "no_data"))
    with_data = [m for m in HEALTH_LABELS if analysis["metrics"].get(m, {}).get("status") in ("stable", "shift_up", "shift_down")]
    changed = [HEALTH_LABELS[m] for m in with_data if analysis["metrics"][m]["status"] != "stable"]
    if not with_data:
        headline = "Faltan datos para evaluar los signos vitales."
    elif changed:
        headline = f"Cambiaron {len(changed)} de {len(with_data)} señales vitales: {', '.join(changed)}."
    else:
        headline = f"Sin cambios en las {len(with_data)} señales vitales con datos suficientes."
    return SpecialistInput("health", facts, analysis["source"], {"gravity_context": analysis["gravity_context"]}, headline)


def build_space_input(analysis: dict) -> SpecialistInput:
    facts = []
    for chamber in analysis["dose"]["chambers"]:
        label = CHAMBER_LABELS.get(chamber["channel"], chamber["channel"])
        text = f"{label}: dosis absorbida acumulada {chamber['latest_value']} {chamber['unit']}."
        flag = ""
        if chamber["counter_decreased"]:
            text += " El contador disminuyó dentro de su época: revisar integridad de datos."
            flag = "counter_decreased"
        rate = chamber.get("rate_per_hour")
        if rate and rate["early"] is not None and rate["recent"] is not None:
            text += f" Ritmo reciente {rate['recent']} {chamber['unit']}/h frente a {rate['early']} {chamber['unit']}/h al inicio."
            if chamber["status"] == "rate_up":
                text += f" Es {chamber['rate_ratio']} veces el ritmo inicial."
                flag = flag or "rate_up"
        elif chamber["status"] == "insufficient_data":
            text += " Pocas lecturas para comparar su ritmo."
        facts.append(Fact(chamber["sensor"], text, flag))
    # Contexto ambiental de la NASA: aparte de la dosimetría personal, y nunca una dosis.
    weather = analysis.get("space_weather") or {}
    events = weather.get("event_count", 0) if weather.get("status") == "ok" else 0
    if weather.get("status") == "ok":
        span = f"entre {weather['start_date']} y {weather['end_date']}"
        if events:
            times = ", ".join(t[:16].replace("T", " ") + " UTC" for t in weather["event_times"][:5])
            text = (
                f"Contexto espacial (NASA DONKI): {events} evento(s) de aumento de radiación en los cinturones (RBE) {span}: {times}. "
                "Es contexto ambiental, no dosis personal."
            )
        else:
            text = f"Contexto espacial (NASA DONKI): sin eventos RBE {span}. Esto no significa radiación cero."
        facts.append(Fact("nasa", text))
    gravity = analysis["gravity_context"]
    if gravity == "unknown":
        facts.append(Fact("gravity", "Contexto de gravedad: no registrado.", "unknown_context"))
    else:
        facts.append(Fact("gravity", f"Contexto de gravedad: {GRAVITY.get(gravity, gravity)}."))
    facts.sort(key=lambda f: f.flag in ("", "unknown_context"))
    chambers = analysis["dose"]["chambers"]
    rising = sum(c["status"] == "rate_up" for c in chambers)
    if not chambers:
        headline = "Sin lecturas del dosímetro."
    elif rising:
        headline = f"El ritmo de dosis subió en {rising} de {len(chambers)} cámaras."
    else:
        headline = f"Sin cambios en el ritmo de dosis ({len(chambers)} cámaras)."
    if any(c["counter_decreased"] for c in chambers):
        headline += " Un contador disminuyó: revisar los datos."
    if events:
        headline += f" La NASA registró {events} evento(s) RBE en la semana hasta la última lectura (contexto, no dosis personal)."
    return SpecialistInput("space", facts, analysis["source"], {"gravity_context": gravity}, headline)
