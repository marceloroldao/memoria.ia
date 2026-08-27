from __future__ import annotations

import itertools
import json

from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96


DOMAINS = {
    "bank": {
        "observe": [
            "cliente envia pagamento banco",
            "comprador transfere dinheiro banco",
            "usuario remete valor instituicao",
            "depositante envia quantia agencia",
            "cliente transfere quantia agencia",
            "depositante remete pagamento banco",
            "banco envia pagamento cliente",
            "instituicao transfere dinheiro comprador",
            "agencia envia quantia depositante",
            "banco remete valor usuario",
        ],
        "roles": {
            "customer": ["cliente", "comprador", "usuario"],
            "transfer": ["paga", "envia", "transfere", "remete"],
            "money": ["dinheiro", "pagamento", "valor"],
            "bank": ["banco", "instituicao"],
        },
        "tokens": {
            "depositante": "customer",
            "remete": "transfer",
            "quantia": "money",
            "agencia": "bank",
        },
        "patterns": [
            ("customer", "transfer", "money", "bank"),
            ("bank", "transfer", "money", "customer"),
        ],
    },
    "sensor": {
        "observe": [
            "sensor mede temperatura ambiente",
            "medidor detecta umidade sala",
            "dispositivo registra pressao recinto",
            "sonda mede calor exterior",
            "sensor detecta calor exterior",
            "sonda registra temperatura ambiente",
            "ambiente fornece temperatura sensor",
            "sala fornece umidade medidor",
            "exterior fornece calor sonda",
            "recinto fornece pressao dispositivo",
        ],
        "roles": {
            "device": ["sensor", "medidor", "dispositivo"],
            "measure": ["mede", "detecta", "registra"],
            "quantity": ["temperatura", "umidade", "pressao"],
            "environment": ["ambiente", "sala", "recinto"],
        },
        "tokens": {
            "sonda": "device",
            "fornece": "measure",
            "calor": "quantity",
            "exterior": "environment",
        },
        "patterns": [
            ("device", "measure", "quantity", "environment"),
            ("environment", "measure", "quantity", "device"),
        ],
    },
    "education": {
        "observe": [
            "professor explica conceito aluno",
            "docente ensina tema estudante",
            "mestre apresenta ideia aprendiz",
            "instrutor explica nocao discente",
            "professor ensina nocao discente",
            "instrutor apresenta conceito aluno",
            "aluno explica conceito professor",
            "estudante ensina tema docente",
            "aprendiz apresenta ideia mestre",
            "discente explica nocao instrutor",
        ],
        "roles": {
            "teacher": ["professor", "docente", "mestre"],
            "explain": ["explica", "ensina", "apresenta"],
            "concept": ["conceito", "tema", "ideia"],
            "student": ["aluno", "estudante", "aprendiz"],
        },
        "tokens": {
            "instrutor": "teacher",
            "explica": "explain",
            "nocao": "concept",
            "discente": "student",
        },
        "patterns": [
            ("teacher", "explain", "concept", "student"),
            ("student", "explain", "concept", "teacher"),
        ],
    },
}


def build_router(spec) -> RoleStructuralRouterV96:
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        role_top_k=4,
        beam_width=256,
        max_context_relabels=4,
    )
    router.observe(spec["observe"])
    for role_id, anchors in spec["roles"].items():
        router.register_role(role_id, anchors)
    return router


def assignment_cost(router: RoleStructuralRouterV96, tokens, pattern):
    total_abs = 0.0
    relabels = 0
    details = []
    for token, target_role in zip(tokens, pattern):
        options = router._rank_role_candidates(token)
        ranked = [(item.role_id, float(item.score)) for item in options]
        if not ranked:
            return None
        top_role, top_score = ranked[0]
        selected = next((score for role, score in ranked if role == target_role), None)
        if selected is None:
            return None
        cost = max(0.0, top_score - selected)
        total_abs += cost
        relabels += int(target_role != top_role)
        details.append({
            "token": token,
            "target_role": target_role,
            "top_role": top_role,
            "top_score": top_score,
            "selected_score": selected,
            "abs_cost": cost,
        })
    return {
        "cost": total_abs,
        "relabels": relabels,
        "details": details,
    }


def evaluate_domain(name, spec):
    router = build_router(spec)
    token_roles = spec["tokens"]
    patterns = [tuple(p) for p in spec["patterns"]]
    rows = []

    for perm in itertools.permutations(token_roles.keys()):
        ground_truth_roles = tuple(token_roles[token] for token in perm)
        is_valid = ground_truth_roles in patterns
        fits = []
        for pattern in patterns:
            measured = assignment_cost(router, perm, pattern)
            if measured is not None:
                fits.append({"pattern": list(pattern), **measured})
        fits.sort(key=lambda row: (row["cost"], row["relabels"], row["pattern"]))
        best = fits[0] if fits else None
        rows.append({
            "tokens": list(perm),
            "ground_truth_roles": list(ground_truth_roles),
            "valid": is_valid,
            "best_fit": best,
        })

    valid_costs = [r["best_fit"]["cost"] for r in rows if r["valid"] and r["best_fit"]]
    invalid_costs = [r["best_fit"]["cost"] for r in rows if not r["valid"] and r["best_fit"]]
    valid_max = max(valid_costs) if valid_costs else None
    invalid_min = min(invalid_costs) if invalid_costs else None
    margin = invalid_min - valid_max if valid_max is not None and invalid_min is not None else None

    cheapest_invalid = sorted(
        (r for r in rows if not r["valid"] and r["best_fit"]),
        key=lambda r: (r["best_fit"]["cost"], r["best_fit"]["relabels"], r["tokens"]),
    )[:5]
    most_expensive_valid = sorted(
        (r for r in rows if r["valid"] and r["best_fit"]),
        key=lambda r: (-r["best_fit"]["cost"], r["tokens"]),
    )[:5]

    return {
        "domain": name,
        "permutations": len(rows),
        "valid_permutations": sum(int(r["valid"]) for r in rows),
        "invalid_permutations": sum(int(not r["valid"]) for r in rows),
        "valid_max_cost": valid_max,
        "invalid_min_cost": invalid_min,
        "separation_margin": margin,
        "separable": margin is not None and margin > 0.0,
        "most_expensive_valid": most_expensive_valid,
        "cheapest_invalid": cheapest_invalid,
    }


def main() -> None:
    domains = [evaluate_domain(name, spec) for name, spec in DOMAINS.items()]
    global_valid_max = max(row["valid_max_cost"] for row in domains if row["valid_max_cost"] is not None)
    global_invalid_min = min(row["invalid_min_cost"] for row in domains if row["invalid_min_cost"] is not None)
    output = {
        "domains": domains,
        "global_valid_max_cost": global_valid_max,
        "global_invalid_min_cost": global_invalid_min,
        "global_separation_margin": global_invalid_min - global_valid_max,
        "globally_separable": global_invalid_min > global_valid_max,
        "midpoint_threshold": (global_invalid_min + global_valid_max) / 2.0,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
