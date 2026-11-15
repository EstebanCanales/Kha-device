"""Engines that produce the specialist reports and the synthesis.

`RulesEngine` is deterministic and needs no model: it is the development and test
default. `OllamaEngine` and `HuggingFaceEngine` run the three models listed in
`ia/README.md`, through a local Ollama server or through transformers.
"""

import gc
import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol

from .contracts import SpecialistInput, SpecialistReport, Summary

# Limitations the models never get to omit: they describe the method, not the readings.
HEALTH_LIMITS = [
    "Compara cada lectura con las primeras de esta misma sesión, no con rangos clínicos.",
    "No es un diagnóstico: requiere validación profesional.",
]
SPACE_LIMITS = [
    "La dosis se muestra tal como la reporta cada cámara; no se convierte a dosis equivalente ni se calcula riesgo.",
    "Cada cámara es un contador propio y sus valores no se suman entre sí.",
]
SIMULATED_NOTE = "Los datos son simulados, no provienen de un instrumento real."


class EngineError(Exception):
    """A failure whose message is safe to show: it never contains prompts, replies, or readings."""


class Engine(Protocol):
    name: str

    def specialist(self, data: SpecialistInput) -> SpecialistReport: ...

    def synthesize(self, health: SpecialistReport, space: SpecialistReport, missing_data: list[str]) -> Summary: ...


def _limits(data: SpecialistInput, base: list[str], extra: list[str] | None = None) -> list[str]:
    limits = [*base, *(extra or [])]
    if data.source == "simulated":
        limits.append(SIMULATED_NOTE)
    if data.context.get("gravity_context") == "unknown":
        limits.append("El contexto de gravedad no está registrado.")
    return limits


def _computed_findings(health: SpecialistReport, space: SpecialistReport) -> list[str]:
    """One computed sentence per specialist, plus a coincidence note only when both found changes."""
    findings = [h for h in (health.headline, space.headline) if h]
    if health.highlights and space.highlights:
        findings.append(
            "Los cambios en signos vitales y en el ritmo de dosis aparecen en la misma ventana de tiempo; "
            "esto no indica que uno cause el otro."
        )
    return findings


class RulesEngine:
    name = "rules"

    def specialist(self, data: SpecialistInput) -> SpecialistReport:
        if not data.facts:
            analysis = "Sin datos suficientes para este análisis."
        else:
            analysis = " ".join(f.text for f in data.facts)
        base = HEALTH_LIMITS if data.kind == "health" else SPACE_LIMITS
        return SpecialistReport(data.kind, analysis, _limits(data, base), self.name, data.highlights, data.headline)

    def synthesize(self, health: SpecialistReport, space: SpecialistReport, missing_data: list[str]) -> Summary:
        # One sentence per specialist; the details stay in each specialist's own report.
        findings = _computed_findings(health, space)
        uncertainties = list(dict.fromkeys([*health.limitations, *space.limitations]))
        return Summary(findings, uncertainties, list(missing_data), self.name)


# --- Language-model engines ---------------------------------------------------------------------

DEFAULT_MODELS = {
    "health": "MohamedAhmedAE/Llama-3.2-3B-Instruct-Medical-Finetuned-merged",
    "astronomy_base": "meta-llama/Llama-3.2-3B-Instruct",
    "astronomy_adapter": "ojayy/llama32-3b-mmlu-astronomy-lora",
    "synthesis": "ibm-granite/granite-3.3-2b-instruct",
}
# Names created by ia/ollama/setup.sh; each can be replaced with any local Ollama tag.
OLLAMA_MODELS = {"health": "kha-health", "space": "kha-astronomy", "synthesis": "granite3.3:2b"}
_RULES = (
    "Only restate which values changed and by how much, using the numbers you are given. "
    "Do NOT explain why they changed, do NOT say what the changes mean, and do NOT mention stress, illness, "
    "danger, risk, or treatment. Do not add numbers that are not in the text. Write the sentences in Spanish "
    "but keep the JSON keys exactly as shown, in English."
)
_EXAMPLE = (
    ' Reply only as JSON, for example: {"analysis": "La frecuencia cardíaca pasó de 70 a 95 lpm.", '
    '"limitations": ["Hay pocas lecturas."]}. "limitations" are at most 2 short caveats, never readings.'
)
SYSTEM = {
    "health": (
        "You restate physiological readings that were already computed, in 2 to 4 sentences. " + _RULES + _EXAMPLE
    ),
    "space": (
        "You restate radiation-dose counters that were already computed, in 2 to 4 sentences. Each chamber is its "
        "own counter: never add them together or convert units. " + _RULES + _EXAMPLE
    ),
    "synthesis": (
        "You join two reports into at most 3 short sentences for a reviewer, using only the text given. "
        + _RULES
        + ' Reply only as JSON: {"findings": ["..."], "uncertainties": ["..."]}.'
    ),
}


def _json_object(text: str) -> dict:
    """The first JSON object in a model reply, or {} when the model did not return valid JSON."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        value = json.loads(text[start : end + 1])
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


_SAME_NUMBER = re.compile(r"\bde\s+(\d+(?:[.,]\d+)?)\b[^.]{0,20}?\ba\s+\1\b")


def _flawed_change(text: str) -> bool:
    """A model saying a value changed "from X to X": the same figure on both sides."""
    return bool(_SAME_NUMBER.search(text.replace(",", ".")))


def _unsupported_numbers(text: str, facts_text: str) -> list[str]:
    """Numbers in a model's text that do not appear (even rounded) in the facts it was given."""
    known = [n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", facts_text)]
    found = []
    for number in re.findall(r"\d+(?:[.,]\d+)?", text):
        value = number.replace(",", ".")
        if value.isdigit() and len(value) == 1:
            continue  # counts such as "2 cámaras" are not readings
        if not any(k == value or k.startswith(value) for k in known) and value not in found:
            found.append(value)
    return found


_ALIASES = {
    "analysis": ("analysis", "análisis", "analisis"),
    "limitations": ("limitations", "limitaciones"),
    "findings": ("findings", "hallazgos"),
    "uncertainties": ("uncertainties", "incertidumbres"),
}


def _pick(parsed: dict, key: str):
    """A value from a model's JSON, tolerating keys the model translated into Spanish."""
    for name in _ALIASES[key]:
        if name in parsed:
            return parsed[name]
    return None


def _loose_strings(reply: str) -> list[str]:
    """Sentences from a reply whose JSON could not be parsed (for example, cut off at the token limit)."""
    items = re.findall(r'"((?:[^"\\]|\\.){25,})"', reply)
    return [i.replace("\\n", " ").strip() for i in items if i.strip()] or [re.sub(r'[{}\[\]"]', "", reply).strip()]


def reply_analysis(reply: str) -> str:
    """The analysis text in a specialist's reply (JSON or loose), as the model wrote it."""
    parsed = _json_object(reply)
    text = _pick(parsed, "analysis") if parsed else " ".join(_loose_strings(reply))
    if isinstance(text, list):  # some models answer with a list of sentences instead of one string
        text = " ".join(str(item) for item in text)
    return text.strip()[:2000] if isinstance(text, str) else ""


def reply_findings(reply: str) -> list[str]:
    """The synthesis sentences in a reply, as the model wrote them."""
    parsed = _json_object(reply)
    return _strings(_pick(parsed, "findings"), 3) or _strings(_loose_strings(reply), 3)


def _strings(value, limit=8) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [str(v)[:400] for v in value[:limit]] if isinstance(value, list) else []


class LanguageModelEngine:
    """Shared prompts and reply handling. Subclasses only say how to ask one model one question."""

    name = "language-model"

    def _generate(self, role: str, user: str) -> str:
        raise NotImplementedError

    def specialist(self, data: SpecialistInput) -> SpecialistReport:
        base = HEALTH_LIMITS if data.kind == "health" else SPACE_LIMITS
        if not data.facts:
            return SpecialistReport(
                data.kind, "Sin datos suficientes para este análisis.", _limits(data, base), self.name, [], data.headline
            )
        reply = self._generate(data.kind, "\n".join(f"- {f.text}" for f in data.facts))
        parsed = _json_object(reply)
        analysis = reply_analysis(reply)
        facts_text = " ".join(f.text for f in data.facts)
        notes = _strings(_pick(parsed, "limitations"), 2)
        unsupported = _unsupported_numbers(analysis, facts_text) if analysis else []
        if not analysis:
            # An empty or malformed reply is replaced by the computed sentences, and says so.
            analysis = facts_text
            notes.append("El modelo no devolvió texto; se muestran las frases calculadas a partir de las lecturas.")
        elif unsupported or _flawed_change(analysis):
            # A figure that is not in the readings must never reach the screen, not even with a warning.
            why = (
                f"citaba cifras que no están en las lecturas ({', '.join(unsupported[:3])})"
                if unsupported else "describía un cambio entre dos cifras idénticas"
            )
            analysis = facts_text
            notes.append(f"Se descartó el texto del modelo porque {why}; se muestran las frases calculadas.")
        return SpecialistReport(data.kind, analysis, _limits(data, base, notes), self.name, data.highlights, data.headline)

    def synthesize(self, health: SpecialistReport, space: SpecialistReport, missing_data: list[str]) -> Summary:
        user = (
            f"HEALTH REPORT:\n{health.analysis}\nLimitations: {'; '.join(health.limitations)}\n\n"
            f"SPACE REPORT:\n{space.analysis}\nLimitations: {'; '.join(space.limitations)}\n\n"
            f"KNOWN MISSING DATA:\n{'; '.join(missing_data) or 'none'}"
        )
        reply = self._generate("synthesis", user)
        parsed = _json_object(reply)
        reports_text = f"{health.analysis} {space.analysis} {health.headline} {space.headline}"
        narrative, dropped = [], 0
        for line in reply_findings(reply):
            if _unsupported_numbers(line, reports_text) or _flawed_change(line):
                dropped += 1
            else:
                narrative.append(line)
        # Findings and missing data come from the readings only. A model may phrase things, never add facts to them.
        uncertainties = list(dict.fromkeys([*health.limitations, *space.limitations, *_strings(_pick(parsed, "uncertainties"), 3)]))
        if dropped:
            uncertainties.append(
                f"Se descartaron {dropped} frase(s) de la lectura del modelo por citar cifras que no están en los informes "
                "o describir un cambio entre dos cifras idénticas."
            )
        return Summary(_computed_findings(health, space), uncertainties, list(missing_data), self.name, narrative)


class OllamaEngine(LanguageModelEngine):
    """Runs the three models through a local Ollama server (`ollama serve`) over its HTTP API.

    Ollama keeps models loaded for `IA_OLLAMA_KEEP_ALIVE` and frees them afterwards, so the three
    do not need to fit in memory together.
    """

    name = "ollama"

    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        if "://" not in self.host:
            self.host = "http://" + self.host
        self.models = {k: os.getenv(f"IA_OLLAMA_MODEL_{k.upper()}", v) for k, v in OLLAMA_MODELS.items()}
        self.timeout = float(os.getenv("IA_TIMEOUT", "300"))
        self.keep_alive = os.getenv("IA_OLLAMA_KEEP_ALIVE", "5m")
        self.max_new_tokens = int(os.getenv("IA_MAX_NEW_TOKENS", "700"))

    def _generate(self, role: str, user: str) -> str:
        model = self.models[role]
        body = json.dumps({
            "model": model, "stream": False, "format": "json", "keep_alive": self.keep_alive,
            "messages": [{"role": "system", "content": SYSTEM[role]}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "num_predict": self.max_new_tokens},
        }).encode()
        request = urllib.request.Request(
            self.host.rstrip("/") + "/api/chat", data=body, method="POST", headers={"Content-Type": "application/json"}
        )
        # Never put the prompt or the reply in an error message: they contain physiological values.
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)["message"]["content"]
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise EngineError(
                    f"Ollama no tiene el modelo «{model}». Prepáralo con ia/ollama/setup.sh o cambia IA_OLLAMA_MODEL_{role.upper()}."
                ) from error
            raise EngineError(f"Ollama respondió con el error {error.code} para el modelo «{model}».") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            raise EngineError(
                f"No se pudo hablar con Ollama en {self.host}. ¿Está corriendo `ollama serve`? "
                f"(Con modelos grandes, el primer uso puede superar el límite de {self.timeout:.0f} s: IA_TIMEOUT.)"
            ) from error
        except (KeyError, ValueError) as error:
            raise EngineError(f"Ollama devolvió una respuesta que no se pudo leer para «{model}».") from error


class HuggingFaceEngine(LanguageModelEngine):
    """Loads one model at a time unless IA_KEEP_LOADED=true, so the three never need to fit together."""

    name = "huggingface"

    def __init__(self):
        self.models = {k: os.getenv(f"IA_MODEL_{k.upper()}", v) for k, v in DEFAULT_MODELS.items()}
        self.keep = os.getenv("IA_KEEP_LOADED", "false").lower() == "true"
        self.max_new_tokens = int(os.getenv("IA_MAX_NEW_TOKENS", "400"))
        self._loaded: dict[str, tuple] = {}

    def _load(self, role: str):
        if role in self._loaded:
            return self._loaded[role]
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise EngineError("Install the optional group first: uv sync --extra ia") from error
        device_map = os.getenv("IA_DEVICE", "auto")
        if role == "space":
            from peft import PeftModel

            base = AutoModelForCausalLM.from_pretrained(self.models["astronomy_base"], device_map=device_map, torch_dtype="auto")
            model = PeftModel.from_pretrained(base, self.models["astronomy_adapter"])
            tokenizer = AutoTokenizer.from_pretrained(self.models["astronomy_base"])
        else:
            repo = self.models["health" if role == "health" else "synthesis"]
            model = AutoModelForCausalLM.from_pretrained(repo, device_map=device_map, torch_dtype="auto")
            tokenizer = AutoTokenizer.from_pretrained(repo)
        if self.keep:
            self._loaded[role] = (model, tokenizer)
        return model, tokenizer

    def _generate(self, role: str, user: str) -> str:
        model, tokenizer = self._load(role)
        messages = [{"role": "system", "content": SYSTEM[role]}, {"role": "user", "content": user}]
        inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        inputs = inputs.to(model.device)
        output = model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        reply = tokenizer.decode(output[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
        if not self.keep:
            del model, tokenizer, inputs, output
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
        return reply


ENGINE_LABELS = {"rules": "Motor de reglas", "ollama": "Modelos en Ollama", "huggingface": "Modelos Hugging Face"}


def describe_engine() -> dict:
    """Which engine is configured, for display. Reads no model and exposes no credential."""
    choice = os.getenv("IA_ENGINE", "rules").lower()
    if choice == "ollama":
        m = {k: os.getenv(f"IA_OLLAMA_MODEL_{k.upper()}", v) for k, v in OLLAMA_MODELS.items()}
        labels = {"health": m["health"], "space": m["space"], "synthesis": m["synthesis"]}
    elif choice == "huggingface":
        m = {k: os.getenv(f"IA_MODEL_{k.upper()}", v) for k, v in DEFAULT_MODELS.items()}
        labels = {"health": m["health"], "space": f"{m['astronomy_adapter']} sobre {m['astronomy_base']}", "synthesis": m["synthesis"]}
    else:
        return {"engine": "rules", "label": ENGINE_LABELS["rules"], "real_models": False, "labels": {}}
    return {"engine": choice, "label": ENGINE_LABELS[choice], "real_models": True, "labels": labels}


def get_engine() -> Engine:
    choice = os.getenv("IA_ENGINE", "rules").lower()
    if choice == "rules":
        return RulesEngine()
    if choice == "ollama":
        return OllamaEngine()
    if choice == "huggingface":
        return HuggingFaceEngine()
    raise ValueError("IA_ENGINE must be 'rules', 'ollama', or 'huggingface'.")
