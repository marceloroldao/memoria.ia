from __future__ import annotations

import itertools
import json

from benchmarks.role_joint_boundary_trajectory_edges import build_edge_router, edge_directional_score
from benchmarks.role_joint_self_calibration import calibration_rows


def fit_direction(rows):
    valid = [r for r in rows if r["valid"]]
    invalid = [r for r in rows if not r["valid"]]
    if not valid or not invalid:
        return {"separable": False, "reason": "insufficient calibration classes"}
    vmin = min(r["edge_direction"] for r in valid)
    imax = max(r["edge_direction"] for r in invalid)
    margin = vmin - imax
    return {
        "threshold": (vmin + imax) / 2.0,
        "margin": margin,
        "separable": margin > 0.0,
    }


def novel_permutation_rows(router, spec):
    token_roles = spec["tokens"]
    patterns = [tuple(p) for p in spec["patterns"]]
    pattern_set = set(patterns)
    rows = []
    for perm in itertools.permutations(token_roles.keys()):
        roles = tuple(token_roles[t] for t in perm)
        rows.append({
            "tokens": list(perm),
            "valid": roles in pattern_set,
            "edge_direction": edge_directional_score(router, perm),
        })
    return rows


def evaluate(rows, boundary):
    if not boundary.get("separable"):
        return {"fail_closed": True, "usable": len(rows), "accepted": 0}
    tp = tn = fp = fn = 0
    errors = []
    for row in rows:
        pred = row["edge_direction"] > boundary["threshold"]
        if row["valid"] and pred:
            tp += 1
        elif row["valid"]:
            fn += 1
        elif pred:
            fp += 1
        else:
            tn += 1
        if pred != row["valid"]:
            errors.append({**row, "predicted_valid": pred})
    return {
        "fail_closed": False,
        "usable": len(rows),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "accuracy": (tp + tn) / max(1, len(rows)),
        "errors": errors,
    }


def spec3():
    return {
        "observe": [
            "autor publica livro", "escritor lanca obra", "poeta divulga texto",
            "editor publica texto", "autor lanca texto", "editor divulga livro",
            "livro recebe autor", "obra recebe escritor", "texto recebe poeta",
        ],
        "roles": {
            "actor": ["autor", "escritor", "poeta"],
            "action": ["publica", "lanca", "divulga"],
            "object": ["livro", "obra", "texto"],
        },
        "tokens": {"editor": "actor", "recebe": "action", "volume": "object"},
        "patterns": [("actor", "action", "object"), ("object", "action", "actor")],
    }


def spec5():
    return {
        "observe": [
            "medico envia exame seguro rede hospital",
            "doutor transmite laudo cifrado canal clinica",
            "especialista remete imagem protegida enlace laboratorio",
            "profissional envia registro privado rota centro",
            "medico transmite registro privado rota centro",
            "centro recebe registro privado rota profissional",
            "hospital recebe exame seguro rede medico",
            "clinica recebe laudo cifrado canal doutor",
            "laboratorio recebe imagem protegida enlace especialista",
        ],
        "roles": {
            "source": ["medico", "doutor", "especialista"],
            "action": ["envia", "transmite", "remete"],
            "payload": ["exame", "laudo", "imagem"],
            "quality": ["seguro", "cifrado", "protegida"],
            "destination": ["hospital", "clinica", "laboratorio"],
        },
        "tokens": {"profissional": "source", "recebe": "action", "registro": "payload", "privado": "quality", "centro": "destination"},
        "patterns": [("source", "action", "payload", "quality", "destination"), ("destination", "action", "payload", "quality", "source")],
    }


def contradictory_spec():
    spec = spec3()
    spec = {k: (list(v) if k == "observe" else v) for k, v in spec.items()}
    spec["observe"] = list(spec["observe"]) + [
        "livro publica autor", "obra lanca escritor", "texto divulga poeta",
        "publica autor livro", "lanca escritor obra", "divulga poeta texto",
    ]
    return spec


def single_anchor_spec():
    return {
        "observe": ["fonte move dado destino", "destino move dado fonte"],
        "roles": {
            "source": ["fonte"], "action": ["move"], "payload": ["dado"], "destination": ["destino"],
        },
        "tokens": {"origem": "source", "leva": "action", "conteudo": "payload", "alvo": "destination"},
        "patterns": [("source", "action", "payload", "destination"), ("destination", "action", "payload", "source")],
    }


def insertion_deletion_rows(router, spec):
    tokens = list(spec["tokens"].keys())
    valid_patterns = [tuple(p) for p in spec["patterns"]]
    rows = []
    # Every deletion of one token from an otherwise valid novel trajectory is invalid.
    valid_sequences = []
    token_by_role = {role: token for token, role in spec["tokens"].items()}
    for pattern in valid_patterns:
        seq = tuple(token_by_role[r] for r in pattern)
        valid_sequences.append(seq)
        for idx in range(len(seq)):
            shortened = seq[:idx] + seq[idx + 1:]
            rows.append({"kind": "deletion", "tokens": list(shortened), "valid": False, "edge_direction": edge_directional_score(router, shortened)})
        for idx in range(len(seq) + 1):
            inserted = seq[:idx] + ("intruso",) + seq[idx:]
            rows.append({"kind": "insertion", "tokens": list(inserted), "valid": False, "edge_direction": edge_directional_score(router, inserted)})
    for seq in valid_sequences:
        rows.append({"kind": "valid", "tokens": list(seq), "valid": True, "edge_direction": edge_directional_score(router, seq)})
    return rows


def run(name, spec, *, alterations=False):
    n = len(next(iter(spec["patterns"])))
    router = build_edge_router(spec, role_top_k=max(4, n), beam_width=4096 if n >= 5 else 256, max_context_relabels=n)
    calibration = calibration_rows(router, spec)
    boundary = fit_direction(calibration)
    permutations = evaluate(novel_permutation_rows(router, spec), boundary)
    result = {
        "name": name,
        "length": n,
        "calibration_examples": len(calibration),
        "calibration_valid": sum(r["valid"] for r in calibration),
        "calibration_invalid": sum(not r["valid"] for r in calibration),
        "boundary": boundary,
        "permutations": permutations,
    }
    if alterations:
        result["insert_delete"] = evaluate(insertion_deletion_rows(router, spec), boundary)
    return result


def main():
    cases = [
        run("length3", spec3(), alterations=True),
        run("length5", spec5(), alterations=True),
        run("contradictory_length3", contradictory_spec(), alterations=True),
        run("single_anchor_fail_closed", single_anchor_spec(), alterations=True),
    ]
    print(json.dumps({
        "method": "BOS/EOS signed trajectory support only; leave-one-anchor-out calibration",
        "cases": cases,
        "summary": {
            "length3_perfect": cases[0]["permutations"].get("accuracy") == 1.0,
            "length5_perfect": cases[1]["permutations"].get("accuracy") == 1.0,
            "length3_alterations_rejected": cases[0]["insert_delete"].get("fp", 0) == 0,
            "length5_alterations_rejected": cases[1]["insert_delete"].get("fp", 0) == 0,
            "contradictory_calibration_separable": cases[2]["boundary"].get("separable", False),
            "single_anchor_fail_closed": cases[3]["permutations"].get("fail_closed", False),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
