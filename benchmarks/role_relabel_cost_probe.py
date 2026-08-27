from __future__ import annotations

import json
from dataclasses import dataclass

from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96
from memoria_resolutiva.textual import tokenize


STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e",
    "em", "na", "nas", "no", "nos", "o", "os", "para", "por", "sem", "um", "uma",
}


@dataclass(frozen=True)
class Case:
    domain: str
    kind: str
    text: str
    target: tuple[str, ...]


def bank_router() -> RoleStructuralRouterV96:
    r = RoleStructuralRouterV96(max_context_relabels=4, role_threshold=0.30, role_min_margin=0.02)
    r.observe([
        "cliente envia pagamento banco", "comprador transfere dinheiro banco",
        "usuario remete valor instituicao", "depositante envia quantia agencia",
        "cliente transfere quantia agencia", "depositante remete pagamento banco",
        "banco envia pagamento cliente", "instituicao transfere dinheiro comprador",
        "agencia envia quantia depositante", "banco remete valor usuario",
    ])
    r.register_role("customer", ["cliente", "comprador", "usuario"])
    r.register_role("transfer", ["paga", "envia", "transfere", "remete"])
    r.register_role("money", ["dinheiro", "pagamento", "valor"])
    r.register_role("bank", ["banco", "instituicao"])
    return r


def sensor_router() -> RoleStructuralRouterV96:
    r = RoleStructuralRouterV96(max_context_relabels=4, role_threshold=0.30, role_min_margin=0.02)
    r.observe([
        "sensor mede temperatura ambiente", "medidor detecta umidade sala",
        "dispositivo registra pressao recinto", "sonda mede calor exterior",
        "sensor detecta calor exterior", "sonda registra temperatura ambiente",
        "ambiente fornece temperatura sensor", "sala fornece umidade medidor",
        "exterior fornece calor sonda", "recinto fornece pressao dispositivo",
    ])
    r.register_role("device", ["sensor", "medidor", "dispositivo"])
    r.register_role("measure", ["mede", "detecta", "registra"])
    r.register_role("quantity", ["temperatura", "umidade", "pressao"])
    r.register_role("environment", ["ambiente", "sala", "recinto"])
    return r


def education_router() -> RoleStructuralRouterV96:
    r = RoleStructuralRouterV96(max_context_relabels=4, role_threshold=0.30, role_min_margin=0.02)
    r.observe([
        "professor explica conceito aluno", "docente ensina tema estudante",
        "mestre apresenta ideia aprendiz", "instrutor explica nocao discente",
        "professor ensina nocao discente", "instrutor apresenta conceito aluno",
        "aluno explica conceito professor", "estudante ensina tema docente",
        "aprendiz apresenta ideia mestre", "discente explica nocao instrutor",
    ])
    r.register_role("teacher", ["professor", "docente", "mestre"])
    r.register_role("explain", ["explica", "ensina", "apresenta"])
    r.register_role("concept", ["conceito", "tema", "ideia"])
    r.register_role("student", ["aluno", "estudante", "aprendiz"])
    return r


def score_assignment(router: RoleStructuralRouterV96, text: str, target: tuple[str, ...]):
    tokens = [t for t in tokenize(text.strip().lower()) if t not in STOPWORDS]
    if len(tokens) != len(target):
        return {"possible": False, "reason": "length", "tokens": tokens}

    total_abs = 0.0
    total_rel = 0.0
    relabels = 0
    details = []
    for token, role in zip(tokens, target):
        options = router._rank_role_candidates(token)
        ranked = [(o.role_id, float(o.score)) for o in options]
        if not ranked:
            return {"possible": False, "reason": f"no_candidates:{token}", "tokens": tokens}
        top_role, top_score = ranked[0]
        selected = next((score for rid, score in ranked if rid == role), None)
        if selected is None:
            return {
                "possible": False,
                "reason": f"target_not_candidate:{token}:{role}",
                "tokens": tokens,
                "details": details,
            }
        abs_cost = max(0.0, top_score - selected)
        rel_cost = abs_cost / top_score if top_score > 0 else 0.0
        changed = role != top_role
        relabels += int(changed)
        total_abs += abs_cost
        total_rel += rel_cost
        details.append({
            "token": token,
            "target_role": role,
            "top_role": top_role,
            "top_score": top_score,
            "selected_score": selected,
            "abs_cost": abs_cost,
            "relative_cost": rel_cost,
            "relabel": changed,
            "ranking": ranked,
        })
    return {
        "possible": True,
        "tokens": tokens,
        "relabels": relabels,
        "total_abs_cost": total_abs,
        "total_relative_cost": total_rel,
        "mean_relative_cost": total_rel / len(tokens),
        "details": details,
    }


def main() -> None:
    routers = {
        "bank": bank_router(),
        "sensor": sensor_router(),
        "education": education_router(),
    }
    cases = [
        Case("bank", "valid", "depositante remete quantia para agencia", ("customer", "transfer", "money", "bank")),
        Case("bank", "valid", "agencia remete quantia para depositante", ("bank", "transfer", "money", "customer")),
        Case("bank", "adversarial", "quantia remete depositante agencia", ("bank", "transfer", "money", "customer")),
        Case("sensor", "valid", "sonda mede calor exterior", ("device", "measure", "quantity", "environment")),
        Case("sensor", "valid", "exterior fornece calor sonda", ("environment", "measure", "quantity", "device")),
        Case("sensor", "adversarial", "exterior calor fornece sonda", ("environment", "measure", "quantity", "device")),
        Case("education", "valid", "instrutor explica nocao discente", ("teacher", "explain", "concept", "student")),
        Case("education", "valid", "discente explica nocao instrutor", ("student", "explain", "concept", "teacher")),
        Case("education", "adversarial", "nocao explica instrutor discente", ("student", "explain", "concept", "teacher")),
    ]

    rows = []
    for case in cases:
        measured = score_assignment(routers[case.domain], case.text, case.target)
        rows.append({
            "domain": case.domain,
            "kind": case.kind,
            "text": case.text,
            "target": list(case.target),
            **measured,
        })

    possible_valid = [r for r in rows if r["kind"] == "valid" and r.get("possible")]
    possible_adv = [r for r in rows if r["kind"] == "adversarial" and r.get("possible")]
    output = {
        "rows": rows,
        "valid_max_abs_cost": max((r["total_abs_cost"] for r in possible_valid), default=None),
        "valid_max_relative_cost": max((r["total_relative_cost"] for r in possible_valid), default=None),
        "adversarial_min_abs_cost": min((r["total_abs_cost"] for r in possible_adv), default=None),
        "adversarial_min_relative_cost": min((r["total_relative_cost"] for r in possible_adv), default=None),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
