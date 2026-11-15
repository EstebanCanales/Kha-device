import json
import os
import urllib.error
from unittest import TestCase, mock

from .backends import (
    HuggingFaceEngine,
    OllamaEngine,
    RulesEngine,
    _json_object,
    describe_engine,
    get_engine,
)
from .contracts import MAX_FACT_CHARS, Fact, SpecialistInput
from .evaluation import (
    BROKEN_SPANISH,
    INTERPRETATION,
    make_case,
    score_specialist,
    score_synthesis,
)
from .inputs import build_health_input, build_space_input, describe_missing
from .pipeline import IAError, run_pipeline


def analysis(**overrides):
    base = {
        "session": "s", "source": "simulated", "participant": "synthetic", "gravity_context": "unknown",
        "metrics": {
            "heart_rate": {"status": "shift_up", "unit": "bpm", "z_score": 9.5, "readings": 40,
                           "baseline": {"median": 70.0}, "recent": {"median": 95.0}},
            "spo2": {"status": "stable", "unit": "%", "z_score": 0.1, "readings": 40,
                     "baseline": {"median": 97.0}, "recent": {"median": 97.0}},
            "respiratory_rate": {"status": "no_data"},
            "skin_temperature": {"status": "insufficient_data", "readings": 4},
        },
        "dose": {"chambers": [{
            "sensor": "cad-dis-high-001", "channel": "dis_high", "unit": "mGy", "latest_value": 0.26,
            "counter_decreased": False, "status": "rate_up", "rate_ratio": 5.8,
            "rate_per_hour": {"early": 0.02, "recent": 0.12},
        }]},
        "missing_data": [{"code": "missing_readings", "metric": "heart_rate", "count": 2}],
    }
    base.update(overrides)
    return base


class FakeHF(HuggingFaceEngine):
    """Skips model loading: returns canned replies so parsing and merging can be tested."""

    def __init__(self, replies):
        super().__init__()
        self.replies = replies

    def _generate(self, role, user):
        return self.replies[role]


class InputTests(TestCase):
    def test_changes_come_first_and_are_flagged(self):
        facts = build_health_input(analysis()).facts
        self.assertEqual(facts[0].key, "heart_rate")
        self.assertEqual(facts[0].flag, "shift_up")
        self.assertIn("subió", facts[0].text)
        self.assertIn("lpm", facts[0].text)

    def test_missing_and_short_series_are_stated_not_invented(self):
        text = " ".join(f.text for f in build_health_input(analysis()).facts)
        self.assertIn("sin lecturas válidas", text)
        self.assertIn("solo 4 lecturas", text)

    def test_space_input_keeps_each_chamber_separate_and_flags_unknown_gravity(self):
        data = build_space_input(analysis())
        self.assertIn("alta resolución", data.facts[0].text)
        self.assertEqual(data.facts[0].flag, "rate_up")
        self.assertEqual(data.facts[-1].flag, "unknown_context")

    def test_missing_data_is_described_in_spanish(self):
        self.assertEqual(describe_missing(analysis()), ["Frecuencia cardíaca: 2 lectura(s) ausente(s) por señal perdida."])

    def test_oversized_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            SpecialistInput("health", [Fact("k", "x" * (MAX_FACT_CHARS + 1))], "simulated")
        with self.assertRaises(ValueError):
            SpecialistInput("health", [Fact("k", "x")] * 41, "simulated")


class SpaceContextTests(TestCase):
    def weather(self, **extra):
        base = {"status": "ok", "start_date": "2026-11-09", "end_date": "2026-11-15", "event_count": 0, "event_times": []}
        return {**base, **extra}

    def test_events_are_stated_as_environment_context_not_dose(self):
        data = build_space_input(analysis(space_weather=self.weather(event_count=2, event_times=["2026-11-13T05:14Z", "2026-11-14T22:40Z"])))
        fact = next(f for f in data.facts if f.key == "nasa")
        self.assertIn("2 evento(s)", fact.text)
        self.assertIn("2026-11-13 05:14 UTC", fact.text)
        self.assertIn("no dosis personal", fact.text)
        self.assertIn("La NASA registró 2 evento(s) RBE", data.headline)

    def test_no_events_does_not_claim_zero_radiation(self):
        data = build_space_input(analysis(space_weather=self.weather()))
        fact = next(f for f in data.facts if f.key == "nasa")
        self.assertIn("sin eventos RBE", fact.text)
        self.assertIn("no significa radiación cero", fact.text)
        self.assertNotIn("La NASA registró", data.headline)

    def test_without_nasa_context_nothing_is_added(self):
        for weather in (None, {"status": "not_configured"}, {"status": "unavailable"}):
            data = build_space_input(analysis(space_weather=weather) if weather else analysis())
            self.assertFalse(any(f.key == "nasa" for f in data.facts), weather)

    def test_the_context_reaches_the_summary_and_the_nasa_dates_are_not_flagged_as_invented_figures(self):
        engine = FakeHF({
            "health": "{}",
            "space": json.dumps({"analysis": "La NASA registró 2 eventos entre 2026-11-09 y 2026-11-15.", "limitations": []}),
            "synthesis": "{}",
        })
        result = run_pipeline(analysis(space_weather=self.weather(event_count=2, event_times=["2026-11-13T05:14Z"])), engine)
        self.assertIn("La NASA registró 2 eventos", result["space"]["analysis"])
        self.assertFalse(any("Se descartó" in n for n in result["space"]["limitations"]))


class PipelineTests(TestCase):
    def test_rules_engine_reports_changes_limits_and_missing_data(self):
        result = run_pipeline(analysis(), RulesEngine())
        self.assertEqual(result["engine"], "rules")
        findings = result["summary"]["findings"]
        self.assertEqual(findings[0], "Cambiaron 1 de 2 señales vitales: Frecuencia cardíaca.")
        self.assertEqual(findings[1], "El ritmo de dosis subió en 1 de 1 cámaras.")
        self.assertIn("no indica que uno cause el otro", findings[2])
        self.assertEqual(len(findings), 3)
        self.assertTrue(any("no es un diagnóstico" in u.lower() for u in result["summary"]["uncertainties"]))
        self.assertTrue(any("simulados" in u for u in result["summary"]["uncertainties"]))
        self.assertEqual(len(result["summary"]["missing_data"]), 1)
        self.assertIn("diagnóstico", result["disclaimer"])

    def test_no_changes_gives_an_explicit_negative_finding(self):
        quiet = analysis()
        quiet["metrics"]["heart_rate"].update(status="stable")
        quiet["dose"]["chambers"][0].update(status="stable")
        findings = run_pipeline(quiet, RulesEngine())["summary"]["findings"]
        self.assertEqual(len(findings), 2)
        self.assertIn("Sin cambios en las 2 señales vitales", findings[0])
        self.assertIn("Sin cambios en el ritmo de dosis", findings[1])

    def test_engine_errors_become_ia_error_without_prompt_text(self):
        class Broken(RulesEngine):
            def specialist(self, data):
                raise RuntimeError("secret value 96 bpm")

        with self.assertRaises(IAError) as caught:
            run_pipeline(analysis(), Broken())
        self.assertNotIn("96", str(caught.exception))

    def test_unknown_engine_name_is_rejected(self):
        with mock.patch.dict(os.environ, {"IA_ENGINE": "nope"}), self.assertRaises(ValueError):
            get_engine()


class DescribeEngineTests(TestCase):
    def test_default_is_rules_without_models(self):
        with mock.patch.dict(os.environ, {"IA_ENGINE": "rules"}):
            self.assertEqual(
                describe_engine(), {"engine": "rules", "label": "Motor de reglas", "real_models": False, "labels": {}}
            )

    def test_huggingface_lists_the_three_models_and_no_credentials(self):
        with mock.patch.dict(os.environ, {"IA_ENGINE": "huggingface", "HF_TOKEN": "secret-token"}):
            info = describe_engine()
        self.assertTrue(info["real_models"])
        self.assertEqual(set(info["labels"]), {"health", "space", "synthesis"})
        self.assertIn("astronomy-lora", info["labels"]["space"])
        self.assertNotIn("secret-token", json.dumps(info))


    def test_ollama_lists_its_local_model_names(self):
        with mock.patch.dict(os.environ, {"IA_ENGINE": "ollama"}):
            info = describe_engine()
        self.assertEqual(info["labels"], {"health": "kha-health", "space": "kha-astronomy", "synthesis": "granite3.3:2b"})
        self.assertEqual(info["label"], "Modelos en Ollama")


class FakeResponse:
    def __init__(self, content):
        self.payload = json.dumps({"message": {"content": content}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *a):
        return self.payload


class OllamaEngineTests(TestCase):
    def run_pipeline_with(self, replies):
        """Pretend to be the Ollama server: answer by the model name in the request."""
        sent = []

        def fake_urlopen(request, timeout=None):
            body = json.loads(request.data)
            sent.append(body)
            return FakeResponse(replies[body["model"]])

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            return run_pipeline(analysis(), OllamaEngine()), sent

    def test_each_role_is_sent_to_its_own_model_with_a_deterministic_json_request(self):
        result, sent = self.run_pipeline_with({
            "kha-health": json.dumps({"analysis": "Subió el pulso.", "limitations": ["Pocas lecturas."]}),
            "kha-astronomy": json.dumps({"analysis": "Dosis en aumento.", "limitations": []}),
            "granite3.3:2b": json.dumps({"findings": ["Hay cambios."], "uncertainties": [], "missing_data": []}),
        })
        self.assertEqual([r["model"] for r in sent], ["kha-health", "kha-astronomy", "granite3.3:2b"])
        self.assertTrue(all(r["format"] == "json" and r["stream"] is False and r["options"]["temperature"] == 0 for r in sent))
        self.assertEqual(result["engine"], "ollama")
        self.assertEqual(result["health"]["analysis"], "Subió el pulso.")
        self.assertEqual(result["summary"]["findings"][0], "Cambiaron 1 de 2 señales vitales: Frecuencia cardíaca.")
        self.assertEqual(result["summary"]["narrative"], ["Hay cambios."])
        self.assertNotIn("Hay cambios.", result["summary"]["findings"], "model wording stays out of computed findings")

    def test_synthesis_prompt_carries_both_reports_and_no_identifiers(self):
        _, sent = self.run_pipeline_with({"kha-health": "{}", "kha-astronomy": "{}", "granite3.3:2b": "{}"})
        prompt = sent[2]["messages"][1]["content"]
        self.assertIn("HEALTH REPORT", prompt)
        self.assertIn("SPACE REPORT", prompt)
        self.assertNotIn("synthetic", prompt)  # the participant pseudonym is not sent

    def test_connection_failure_gets_an_actionable_message_without_readings(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with self.assertRaises(IAError) as caught:
                run_pipeline(analysis(), OllamaEngine())
        self.assertIn("ollama serve", str(caught.exception))
        self.assertNotIn("95", str(caught.exception))

    def test_missing_model_says_how_to_create_it(self):
        error = urllib.error.HTTPError("http://x", 404, "not found", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(IAError) as caught:
                run_pipeline(analysis(), OllamaEngine())
        self.assertIn("setup.sh", str(caught.exception))
        self.assertIn("kha-health", str(caught.exception))

    def test_ollama_host_without_scheme_is_accepted(self):
        with mock.patch.dict(os.environ, {"OLLAMA_HOST": "127.0.0.1:11434"}):
            self.assertEqual(OllamaEngine().host, "http://127.0.0.1:11434")


class HuggingFaceEngineTests(TestCase):
    def test_json_replies_are_parsed_and_model_wording_stays_separate(self):
        engine = FakeHF({
            "health": json.dumps({"analysis": "La frecuencia subió.", "limitations": ["Solo 40 lecturas."]}),
            "space": "texto libre sin JSON",
            "synthesis": json.dumps({"findings": ["Hay un cambio."], "uncertainties": ["Poca historia."], "missing_data": ["Sin ECG."]}),
        })
        result = run_pipeline(analysis(), engine)
        self.assertEqual(result["health"]["analysis"], "La frecuencia subió.")
        self.assertIn("Solo 40 lecturas.", result["health"]["limitations"])
        self.assertEqual(result["space"]["analysis"], "texto libre sin JSON")
        findings = result["summary"]["findings"]
        self.assertEqual(findings[0], "Cambiaron 1 de 2 señales vitales: Frecuencia cardíaca.", "computed counts lead")
        self.assertEqual(result["summary"]["narrative"], ["Hay un cambio."])
        self.assertIn("Poca historia.", result["summary"]["uncertainties"])
        # A model may phrase things but never add facts: its "missing data" is ignored.
        self.assertEqual(result["summary"]["missing_data"], ["Frecuencia cardíaca: 2 lectura(s) ausente(s) por señal perdida."])

    def test_empty_model_text_falls_back_to_the_computed_sentences(self):
        engine = FakeHF({"health": json.dumps({"analysis": "", "limitations": []}), "space": "{}", "synthesis": "{}"})
        health = run_pipeline(analysis(), engine)["health"]
        self.assertIn("Frecuencia cardíaca: subió", health["analysis"])
        self.assertTrue(any("no devolvió texto" in n for n in health["limitations"]))

    def test_numbers_that_are_not_in_the_readings_are_flagged(self):
        engine = FakeHF({
            "health": json.dumps({"analysis": "El pulso pasó de 70 a 130 lpm.", "limitations": []}),
            "space": json.dumps({"analysis": "Dosis de 0.26 mGy en 2 cámaras.", "limitations": []}),
            "synthesis": "{}",
        })
        result = run_pipeline(analysis(), engine)
        # An invented figure is discarded: the computed sentences are shown instead, and the reason is stated.
        self.assertNotIn("130", result["health"]["analysis"])
        self.assertIn("Frecuencia cardíaca: subió", result["health"]["analysis"])
        self.assertTrue(any("Se descartó" in n and "130" in n for n in result["health"]["limitations"]))
        # Rounded figures and small counts are fine: the text is kept.
        self.assertEqual(result["space"]["analysis"], "Dosis de 0.26 mGy en 2 cámaras.")

    def test_a_change_between_identical_figures_is_flagged(self):
        engine = FakeHF({
            "health": "{}",
            "space": json.dumps({"analysis": "La dosis aumentó de 0.26 mGy a 0.26 mGy.", "limitations": []}),
            "synthesis": json.dumps({"findings": ["El ritmo pasó de 0.12 mGy/h a 0.12 mGy/h."]}),
        })
        result = run_pipeline(analysis(), engine)
        self.assertNotIn("de 0.26 mGy a 0.26", result["space"]["analysis"])
        self.assertTrue(any("cifras idénticas" in n for n in result["space"]["limitations"]))
        self.assertEqual(result["summary"]["narrative"], [], "the identical-figures sentence is dropped")
        self.assertTrue(any("Se descartaron 1 frase" in u for u in result["summary"]["uncertainties"]))

    def test_a_list_of_sentences_is_accepted_as_the_analysis(self):
        engine = FakeHF({
            "health": json.dumps({"analysis": ["El pulso pasó de 70.0 a 95.0 lpm.", "El oxígeno bajó."], "limitations": "Pocas lecturas."}),
            "space": "{}",
            "synthesis": json.dumps({"findings": "Un solo hallazgo como texto."}),
        })
        result = run_pipeline(analysis(), engine)
        self.assertEqual(result["health"]["analysis"], "El pulso pasó de 70.0 a 95.0 lpm. El oxígeno bajó.")
        self.assertIn("Pocas lecturas.", result["health"]["limitations"])
        self.assertEqual(result["summary"]["narrative"], ["Un solo hallazgo como texto."])

    def test_keys_translated_to_spanish_are_still_understood(self):
        engine = FakeHF({
            "health": json.dumps({"análisis": "El pulso pasó de 70.0 a 95.0 lpm.", "limitaciones": ["Pocas lecturas."]}),
            "space": "{}",
            "synthesis": json.dumps({"hallazgos": ["Hay cambios."], "incertidumbres": ["Poca historia."]}),
        })
        result = run_pipeline(analysis(), engine)
        self.assertEqual(result["health"]["analysis"], "El pulso pasó de 70.0 a 95.0 lpm.")
        self.assertIn("Pocas lecturas.", result["health"]["limitations"])
        self.assertEqual(result["summary"]["narrative"], ["Hay cambios."])
        self.assertIn("Poca historia.", result["summary"]["uncertainties"])

    def test_json_cut_off_by_the_token_limit_shows_sentences_not_json_syntax(self):
        cut = '{"findings": ["La frecuencia cardíaca aumentó de 70.0 a 95.0 lpm en la sesión.", "El ritmo de dosis aumentó en ambas cámaras'
        engine = FakeHF({"health": "{}", "space": "{}", "synthesis": cut})
        narrative = run_pipeline(analysis(), engine)["summary"]["narrative"]
        self.assertEqual(narrative, ["La frecuencia cardíaca aumentó de 70.0 a 95.0 lpm en la sesión."])
        self.assertFalse(any("{" in n or '"findings"' in n for n in narrative))

    def test_invalid_json_falls_back_to_the_raw_reply(self):
        engine = FakeHF({"health": "{roto", "space": "ok", "synthesis": "Resumen en texto plano."})
        summary = run_pipeline(analysis(), engine)["summary"]
        self.assertEqual(summary["narrative"], ["Resumen en texto plano."])

    def test_json_object_extraction(self):
        self.assertEqual(_json_object('antes {"a": 1} después'), {"a": 1})
        self.assertEqual(_json_object("nada"), {})
        self.assertEqual(_json_object("[1, 2]"), {})



class EvaluationHelperTests(TestCase):
    def test_garbled_spanish_is_detected_and_good_spanish_is_not(self):
        for bad in ("La frecuencia cardñaca subió", "el oxùgeno bajó"):
            self.assertTrue(BROKEN_SPANISH.search(bad), bad)
        for good in ("La frecuencia cardíaca subió", "Año de órbita, niño, señal, información"):
            self.assertIsNone(BROKEN_SPANISH.search(good), good)

    def test_medical_interpretation_is_detected_and_plain_restating_is_not(self):
        self.assertTrue(INTERPRETATION.search("Indica una respuesta del cuerpo a un estrés"))
        self.assertTrue(INTERPRETATION.search("La frecuencia bajó debido a 2 lecturas ausentes"))
        self.assertIsNone(INTERPRETATION.search("La frecuencia cardíaca pasó de 68.1 a 89.15 lpm."))

    def test_specialist_score_flags_an_invented_figure_and_missing_changes(self):
        facts = "Frecuencia cardíaca: subió (68.1 → 89.15 lpm)."
        ok = score_specialist('{"analysis": "Pasó de 68.1 a 89.15 lpm."}', facts, [facts])
        self.assertTrue(all(ok.values()), ok)
        bad = score_specialist('{"analysis": "Llegó a 140 lpm."}', facts, [facts])
        self.assertFalse(bad["cifras_reales"])
        self.assertFalse(bad["menciona_cambios"])
        self.assertFalse(score_specialist("", facts, [])["json"])

    def test_synthesis_score_requires_findings_in_the_json(self):
        self.assertTrue(score_synthesis('{"findings": ["a"]}', "")["json"])
        self.assertFalse(score_synthesis('{"x": 1}', "")["json"])

    def test_the_three_cases_are_valid_inputs_for_the_pipeline(self):
        for name in ("stress", "quiet", "sparse"):
            result = run_pipeline(make_case(name), RulesEngine())
            self.assertEqual(result["engine"], "rules", name)
