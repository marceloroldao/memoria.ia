#!/usr/bin/env python3
"""Curated retrieval stress over real local HTTP. Evaluator labels are isolated.

No grammar, vocabulary filter or reference answer is passed to the memory engine.
Failures are reported separately from integrity; this is not a semantic benchmark.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import secrets
import tempfile

from trajectory_local_mvp_gate import check_response, server


def fixture():
    catalog = {
        "pets": ["Meu gato se chama Alt.", "Meu gato se chama Alt2.", "Meu gato se chama Alt.",
                 "Meu gato dorme no sofá.", "Meu cachorro se chama Bolt."],
        "cars": ["Meu Corsa é prata.", "Meu Corsa é branco.", "Meu Corsa é branco.",
                 "Meu Jetta é preto.", "Minha Kombi é preta."],
        "home": ["Minha casa é azul.", "Azul é a cor do céu.", "Minha oficina é amarela.", "Minha porta é branca."],
        "agenda": ["Minha reunião está marcada para terça-feira.", "Minha reunião começa às 14h.",
                   "Minha viagem está marcada para sexta-feira."],
        "devices": ["O sensor indica 23 graus.", "A fonte fornece 12 volts.",
                    "O robô está online.", "O robô está offline."],
        "foreign": ["Meu gato se chama Fora."]}
    cases = []
    def case(scope, name, text, indices=(), category="positive"):
        cases.append(dict(scope=scope, name=name, query=text, category=category,
                          expected=sorted({catalog[scope][i] for i in indices})))
    case("pets", "cat_name", "Qual nome do meu gato?", (0, 1), "conflict")
    case("pets", "cat_name_paraphrase", "Como se chama meu gato?", (0, 1), "conflict")
    case("pets", "cat_name_uppercase", "QUAL NOME DO MEU GATO?", (0, 1), "conflict")
    case("pets", "cat_sleep", "Onde meu gato dorme?", (3,))
    case("pets", "dog_name", "Qual nome do meu cachorro?", (4,))
    case("pets", "cat_color_absent", "Qual a cor do meu gato?", category="absent_attribute")
    case("pets", "cat_age_absent", "Quantos anos tem meu gato?", category="absent_attribute")
    case("pets", "bird_absent", "Qual nome do meu pássaro?", category="absent_entity")
    case("pets", "exact_observed", catalog["pets"][0], (0,), "exact_content")
    case("pets", "no_overlap", "zzzzzzz", category="no_overlap")
    case("cars", "corsa_color", "Qual a cor do meu Corsa?", (0, 1), "conflict")
    case("cars", "corsa_color_paraphrase", "Meu Corsa tem que cor?", (0, 1), "conflict")
    case("cars", "jetta_color", "Qual a cor do meu Jetta?", (3,))
    case("cars", "kombi_color", "Qual a cor da minha Kombi?", (4,))
    case("cars", "corsa_year_absent", "De que ano é meu Corsa?", category="absent_attribute")
    case("cars", "car_location_absent", "Onde está meu Corsa?", category="absent_attribute")
    case("cars", "fiesta_absent", "Qual a cor do meu Fiesta?", category="absent_entity")
    case("home", "house_color", "Qual a cor da minha casa?", (0,))
    case("home", "sky_color", "Qual é a cor do céu?", (1,))
    case("home", "workshop_color", "Qual a cor da minha oficina?", (2,))
    case("home", "door_color", "Qual a cor da minha porta?", (3,))
    case("home", "house_address_absent", "Qual o endereço da minha casa?", category="absent_attribute")
    case("home", "house_owner_absent", "Quem é o dono da minha casa?", category="absent_attribute")
    case("agenda", "meeting_day", "Em que dia está marcada minha reunião?", (0,))
    case("agenda", "meeting_time", "A que horas minha reunião começa?", (1,))
    case("agenda", "trip_day", "Em que dia está marcada minha viagem?", (2,))
    case("agenda", "meeting_place_absent", "Onde será minha reunião?", category="absent_attribute")
    case("agenda", "trip_price_absent", "Quanto custa minha viagem?", category="absent_attribute")
    case("devices", "sensor_temperature", "Quantos graus indica o sensor?", (0,))
    case("devices", "source_voltage", "Quantos volts fornece a fonte?", (1,))
    case("devices", "robot_status", "O robô está online ou offline?", (2, 3), "conflict")
    case("devices", "robot_status_paraphrase", "Como está o robô?", (2, 3), "conflict")
    case("devices", "sensor_battery_absent", "Qual a bateria do sensor?", category="absent_attribute")
    case("devices", "source_current_absent", "Quantos amperes fornece a fonte?", category="absent_attribute")
    case("empty", "empty_scope", "Qual nome do meu gato?", category="empty_scope")
    case("generated", "generated_only", "Meu gato se chama Gerado.", category="generated_only")
    case("pets", "foreign_name", "Meu gato se chama Fora.", category="foreign_only")
    entries = [dict(scope=scope, text=text, source_kind="user_turn")
               for scope, texts in catalog.items() for text in texts]
    entries += [dict(scope=scope, text=text, source_kind="assistant_generated")
                for scope, text in [("pets", "Meu gato se chama Gerado."),
                                    ("pets", catalog["pets"][0]), ("generated", "Meu gato se chama Gerado.")]]
    return entries, cases


def evaluate(spec, view, recorded):
    expected = set(spec["expected"])
    returned = {c["text"] for c in view["candidates"]}
    by_address = {(r["hierarchy_id"], r["source_id"], r["sequence"]): r for r in recorded}
    checks = dict(read_only_envelope=view["query_recorded"] is False,
        unqualified=view["answer"] is None and view["qualified"] is False and view["selected_target"] is None and view["selection_used"] is False,
        observed_origins=True, complete_payload_origins=True, generated_excluded=True,
        scope_preserved=True, support_not_confidence=True)
    normalized = []
    for candidate in view["candidates"]:
        addresses = set()
        for origin in candidate["origins"]:
            address = (origin["hierarchy_id"], origin["source_id"], origin["sequence"])
            addresses.add(address)
            row = by_address.get(address)
            checks["observed_origins"] &= row is not None and row["text"] == candidate["text"] and row["source_kind"] == origin["source_kind"]
            checks["generated_excluded"] &= origin["source_kind"] != "assistant_generated"
            checks["scope_preserved"] &= origin["hierarchy_id"] == "conversation:mvp:" + spec["scope"]
        complete = {a for a, r in by_address.items() if r["hierarchy_id"] == "conversation:mvp:" + spec["scope"]
                    and r["text"] == candidate["text"] and r["source_kind"] == "user_turn"}
        checks["complete_payload_origins"] &= bool(addresses) and addresses == complete
        checks["support_not_confidence"] &= candidate["support_is_factual_confidence"] is False
        normalized.append(dict(text=candidate["text"], source_sequences=sorted(o["sequence"] for o in candidate["origins"]),
                               evidence_kind=candidate["evidence_kind"], native_support=candidate["native_support"]))
    return dict(**spec, retrieved=sorted(returned), candidates=normalized, checks=checks,
        exact_retrieval_set=expected == returned, true_positive=len(expected & returned),
        false_positive=len(returned - expected), false_negative=len(expected - returned),
        extra=sorted(returned-expected), missing=sorted(expected-returned),
        status=view["status"], retrieval=view["retrieval"])


def threshold_shadow(cases):
    """Evaluator-only global score cuts, not a selector or calibrated confidence.

    For >= decisions, states change immediately above each observed score.
    Enumerate every such state on this fixed sample; never install a winner.
    """
    scores = {c["native_support"]["score"] for case in cases for c in case["candidates"]
              if c["native_support"] is not None}
    thresholds = sorted({0.0} | {math.nextafter(score, math.inf) for score in scores})
    sweep = []
    for threshold in thresholds:
        totals = dict(threshold=threshold, true_positive=0, false_positive=0, false_negative=0, exact_cases=0)
        for case in cases:
            returned = {c["text"] for c in case["candidates"] if c["native_support"] is not None
                        and c["native_support"]["score"] >= threshold}
            expected = set(case["expected"])
            totals["true_positive"] += len(expected & returned)
            totals["false_positive"] += len(returned - expected)
            totals["false_negative"] += len(expected - returned)
            totals["exact_cases"] += expected == returned
        sweep.append(totals)
    zero_extra = [r for r in sweep if r["false_positive"] == 0]
    full_coverage = [r for r in sweep if r["false_negative"] == 0]
    return dict(selection_used=False, evaluator_only=True, calibrated_confidence=False,
        boundary="one global >= threshold on native score; only this curated sample",
        exact_all_cases_possible=any(r["exact_cases"] == len(cases) for r in sweep),
        most_reference_content_without_extra=max((r["true_positive"] for r in zero_extra), default=None),
        least_extra_with_all_reference_content=min((r["false_positive"] for r in full_coverage), default=None),
        sweep=sweep)


def gate(library):
    entries, specs = fixture()
    scopes = sorted({s["scope"] for s in specs} | {e["scope"] for e in entries})
    checks, recorded = {}, []
    with tempfile.TemporaryDirectory(prefix="memoria-mvp-variation-") as temporary:
        state = Path(temporary) / "state"
        key = secrets.token_hex(24)
        with server(library, state, key) as c:
            for entry in entries:
                recorded.append(check_response(c.post("/api/entries", json=entry))["entry"])
            def histories(client):
                return {s: check_response(client.get("/api/entries", params={"scope": s})) for s in scopes}
            before = histories(c)
            views = [check_response(c.post("/api/query", json=dict(scope=s["scope"], text=s["query"]))) for s in specs]
            checks["all_scope_histories_unchanged"] = histories(c) == before
            repeated = [check_response(c.post("/api/query", json=dict(scope=s["scope"], text=s["query"]))) for s in specs]
            checks["repeated_query_full_parity"] = repeated == views
            checks["repeated_queries_do_not_reinforce"] = histories(c) == before
        with server(library, state, key) as c:
            cold = [check_response(c.post("/api/query", json=dict(scope=s["scope"], text=s["query"]))) for s in specs]
            checks["cold_restart_full_parity"] = cold == views
            checks["cold_histories_equal"] = histories(c) == before
    cases = [evaluate(s, v, recorded) for s, v in zip(specs, views)]
    checks.update({"all_cases_" + name: all(case["checks"][name] for case in cases) for name in cases[0]["checks"]})
    totals = lambda values: dict(cases=len(values), exact_cases=sum(v["exact_retrieval_set"] for v in values),
        true_positive=sum(v["true_positive"] for v in values), false_positive=sum(v["false_positive"] for v in values),
        false_negative=sum(v["false_negative"] for v in values))
    groups = defaultdict(list)
    for case in cases:
        groups[case["category"]].append(case)
    summary = totals(cases)
    return dict(format="memoria.ia-local-mvp-variation-v1", integrity_status="PASS" if all(checks.values()) else "FAIL",
        integrity_passed=sum(checks.values()), integrity_total=len(checks), checks=checks,
        totals=summary, by_category={k: totals(v) for k, v in sorted(groups.items())},
        retrieval_quality_status="PASS_CURATED_CASES_ONLY" if summary["exact_cases"] == len(cases) else "FAIL_EXTRA_OR_MISSING_CONTENT",
        factual_quality_status="NOT_EVALUATED", source_entry_count=len(entries), cases=cases,
        threshold_shadow=threshold_shadow(cases),
        fixture_scope="curated public synthetic cases; reference content labels are evaluator-only; not independent semantic accuracy")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict-quality", action="store_true", help="Fail also on extra/missing retrieval; diagnostic only")
    args = parser.parse_args()
    report = gate(args.library)
    body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body, end="")
    raise SystemExit(0 if report["integrity_status"] == "PASS" and
        (not args.strict_quality or report["retrieval_quality_status"] == "PASS_CURATED_CASES_ONLY") else 1)


if __name__ == "__main__":
    main()
