from __future__ import annotations

import itertools
import json
import random

from benchmarks.role_directional_relation_matrix import directional_score
from benchmarks.role_joint_boundary_lodo import best_linear_boundary, evaluate
from benchmarks.role_joint_cost_direction_boundary import rows_for_domain
from benchmarks.role_permutation_cost_matrix import DOMAINS, assignment_cost, build_router
from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96


BOUNDARY_TRAIN_ROWS = [r for name, spec in DOMAINS.items() for r in rows_for_domain(name, spec)]
BOUNDARY = best_linear_boundary(BOUNDARY_TRAIN_ROWS)


def score_row(cost: float, direction: float) -> float:
    return direction - BOUNDARY["lambda"] * cost


def classify_rows(rows):
    return evaluate(rows, BOUNDARY)


def noisy_spec(spec, noise_sentences):
    out = {
        "observe": list(spec["observe"]) + list(noise_sentences),
        "roles": {k: list(v) for k, v in spec["roles"].items()},
        "tokens": dict(spec["tokens"]),
        "patterns": [tuple(p) for p in spec["patterns"]],
    }
    return out


def noise_suite():
    generic_noise = [
        "azul corre pedra rapido",
        "janela observa nuvem distante",
        "musica atravessa campo vazio",
        "objeto move sinal aleatorio",
        "tempo conecta forma abstrata",
        "linha cruza ponto neutro",
        "vento carrega folha longe",
        "luz toca superficie clara",
        "numero segue regra simples",
        "forma ocupa espaco pequeno",
    ]
    results = []
    for ratio in (0, 2, 5, 10):
        domain_results = []
        for name, spec in DOMAINS.items():
            noise = generic_noise[:ratio]
            rows = rows_for_domain(name, noisy_spec(spec, noise))
            domain_results.append({"domain": name, "result": classify_rows(rows)})
        results.append({
            "noise_sentences": ratio,
            "domains": domain_results,
            "all_perfect": all(d["result"]["accuracy"] == 1.0 for d in domain_results),
        })
    return results


def order_stability_suite():
    outputs = []
    for seed in range(10):
        domain_results = []
        for name, spec in DOMAINS.items():
            shuffled = list(spec["observe"])
            random.Random(seed).shuffle(shuffled)
            altered = {
                "observe": shuffled,
                "roles": {k: list(v) for k, v in spec["roles"].items()},
                "tokens": dict(spec["tokens"]),
                "patterns": [tuple(p) for p in spec["patterns"]],
            }
            rows = rows_for_domain(name, altered)
            domain_results.append({"domain": name, "result": classify_rows(rows)})
        outputs.append({
            "seed": seed,
            "all_perfect": all(d["result"]["accuracy"] == 1.0 for d in domain_results),
            "domains": domain_results,
        })
    return outputs


def build_mixed_router():
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        role_top_k=8,
        beam_width=1024,
        max_context_relabels=6,
    )
    combined_observe = []
    prefixed_specs = {}
    for name, spec in DOMAINS.items():
        combined_observe.extend(spec["observe"])
        role_map = {role: f"{name}:{role}" for role in spec["roles"]}
        prefixed_specs[name] = {
            "tokens": dict(spec["tokens"]),
            "patterns": [tuple(role_map[r] for r in p) for p in spec["patterns"]],
            "role_map": role_map,
        }
    router.observe(combined_observe)
    for name, spec in DOMAINS.items():
        for role, anchors in spec["roles"].items():
            router.register_role(f"{name}:{role}", anchors)
    return router, prefixed_specs


def mixed_domain_suite():
    router, prefixed = build_mixed_router()
    rows = []
    for name, spec in DOMAINS.items():
        info = prefixed[name]
        token_roles = spec["tokens"]
        patterns = info["patterns"]
        pattern_set = set(patterns)
        for perm in itertools.permutations(token_roles.keys()):
            ground = tuple(info["role_map"][token_roles[token]] for token in perm)
            fits = []
            for pattern in patterns:
                measured = assignment_cost(router, perm, pattern)
                if measured is not None:
                    fits.append(measured["cost"])
            rows.append({
                "domain": name,
                "tokens": list(perm),
                "valid": ground in pattern_set,
                "cost": min(fits) if fits else None,
                "direction": directional_score(router, perm),
            })
    return classify_rows(rows)


def long_sequence_spec():
    return {
        "observe": [
            "operador envia pacote seguro canal destino",
            "usuario transmite mensagem validada enlace servidor",
            "cliente remete bloco cifrado rota terminal",
            "agente envia dado assinado caminho receptor",
            "operador transmite dado assinado caminho receptor",
            "agente remete pacote seguro canal destino",
            "destino recebe pacote seguro canal operador",
            "servidor recebe mensagem validada enlace usuario",
            "terminal recebe bloco cifrado rota cliente",
            "receptor recebe dado assinado caminho agente",
        ],
        "roles": {
            "source": ["operador", "usuario", "cliente"],
            "action": ["envia", "transmite", "remete"],
            "payload": ["pacote", "mensagem", "bloco"],
            "quality": ["seguro", "validada", "cifrado"],
            "path": ["canal", "enlace", "rota"],
            "destination": ["destino", "servidor", "terminal"],
        },
        "tokens": {
            "agente": "source",
            "recebe": "action",
            "dado": "payload",
            "assinado": "quality",
            "caminho": "path",
            "receptor": "destination",
        },
        "patterns": [
            ("source", "action", "payload", "quality", "path", "destination"),
            ("destination", "action", "payload", "quality", "path", "source"),
        ],
    }


def long_sequence_suite():
    spec = long_sequence_spec()
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        role_top_k=6,
        beam_width=4096,
        max_context_relabels=6,
    )
    router.observe(spec["observe"])
    for role, anchors in spec["roles"].items():
        router.register_role(role, anchors)
    token_roles = spec["tokens"]
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    rows = []
    for perm in itertools.permutations(token_roles.keys()):
        roles = tuple(token_roles[t] for t in perm)
        fits = []
        for pattern in patterns:
            measured = assignment_cost(router, perm, pattern)
            if measured is not None:
                fits.append(measured["cost"])
        rows.append({
            "domain": "long6",
            "tokens": list(perm),
            "valid": roles in pattern_set,
            "cost": min(fits) if fits else None,
            "direction": directional_score(router, perm),
        })
    return classify_rows(rows)


def open_set_suite():
    # Novel tokens should not manufacture a valid candidate cost. This checks the
    # current helper/policy boundary rather than pretending unknown words are known.
    cases = []
    for name, spec in DOMAINS.items():
        router = build_router(spec)
        known = list(spec["tokens"].keys())
        patterns = [tuple(p) for p in spec["patterns"]]
        probes = [
            ("zzzz_novo", known[1], known[2], known[3]),
            (known[0], "zzzz_novo", known[2], known[3]),
            (known[0], known[1], "zzzz_novo", known[3]),
            (known[0], known[1], known[2], "zzzz_novo"),
        ]
        for probe in probes:
            fits = [assignment_cost(router, probe, p) for p in patterns]
            possible = [f for f in fits if f is not None]
            cases.append({
                "domain": name,
                "tokens": list(probe),
                "has_candidate_cost": bool(possible),
                "direction": directional_score(router, probe),
            })
    return {
        "cases": cases,
        "all_rejected_before_joint_gate": all(not c["has_candidate_cost"] for c in cases),
    }


def main():
    noise = noise_suite()
    order = order_stability_suite()
    mixed = mixed_domain_suite()
    long6 = long_sequence_suite()
    open_set = open_set_suite()
    output = {
        "boundary": BOUNDARY,
        "noise": noise,
        "order_stability": order,
        "mixed_domain": mixed,
        "long_sequence_6_roles": long6,
        "open_set": open_set,
        "summary": {
            "noise_all_perfect": all(r["all_perfect"] for r in noise),
            "order_all_perfect": all(r["all_perfect"] for r in order),
            "mixed_perfect": mixed["accuracy"] == 1.0,
            "long6_perfect": long6["accuracy"] == 1.0,
            "open_set_all_rejected": open_set["all_rejected_before_joint_gate"],
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
