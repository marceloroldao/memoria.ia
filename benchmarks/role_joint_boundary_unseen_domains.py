from __future__ import annotations

import json

from benchmarks.role_joint_boundary_lodo import best_linear_boundary, evaluate
from benchmarks.role_joint_cost_direction_boundary import rows_for_domain
from benchmarks.role_permutation_cost_matrix import DOMAINS


UNSEEN = {
    "logistics": {
        "observe": [
            "caminhao entrega pacote deposito",
            "van transporta carga armazem",
            "veiculo leva encomenda terminal",
            "frota entrega mercadoria centro",
            "caminhao transporta mercadoria centro",
            "frota leva pacote deposito",
            "deposito recebe pacote caminhao",
            "armazem recebe carga van",
            "terminal recebe encomenda veiculo",
            "centro recebe mercadoria frota",
        ],
        "roles": {
            "vehicle": ["caminhao", "van", "veiculo"],
            "move": ["entrega", "transporta", "leva"],
            "payload": ["pacote", "carga", "encomenda"],
            "destination": ["deposito", "armazem", "terminal"],
        },
        "tokens": {"frota": "vehicle", "recebe": "move", "mercadoria": "payload", "centro": "destination"},
        "patterns": [("vehicle", "move", "payload", "destination"), ("destination", "move", "payload", "vehicle")],
    },
    "network": {
        "observe": [
            "roteador encaminha pacote servidor",
            "switch envia quadro host",
            "gateway transfere dados destino",
            "nodo encaminha mensagem endpoint",
            "roteador envia mensagem endpoint",
            "nodo transfere pacote servidor",
            "servidor retorna pacote roteador",
            "host retorna quadro switch",
            "destino retorna dados gateway",
            "endpoint retorna mensagem nodo",
        ],
        "roles": {
            "node": ["roteador", "switch", "gateway"],
            "forward": ["encaminha", "envia", "transfere"],
            "payload": ["pacote", "quadro", "dados"],
            "endpoint": ["servidor", "host", "destino"],
        },
        "tokens": {"nodo": "node", "retorna": "forward", "mensagem": "payload", "endpoint": "endpoint"},
        "patterns": [("node", "forward", "payload", "endpoint"), ("endpoint", "forward", "payload", "node")],
    },
    "factory": {
        "observe": [
            "robo monta peca estacao",
            "braco solda componente celula",
            "maquina posiciona modulo linha",
            "atuador monta conjunto bancada",
            "robo solda conjunto bancada",
            "atuador posiciona peca estacao",
            "estacao fornece peca robo",
            "celula fornece componente braco",
            "linha fornece modulo maquina",
            "bancada fornece conjunto atuador",
        ],
        "roles": {
            "machine": ["robo", "braco", "maquina"],
            "operation": ["monta", "solda", "posiciona"],
            "part": ["peca", "componente", "modulo"],
            "station": ["estacao", "celula", "linha"],
        },
        "tokens": {"atuador": "machine", "fornece": "operation", "conjunto": "part", "bancada": "station"},
        "patterns": [("machine", "operation", "part", "station"), ("station", "operation", "part", "machine")],
    },
}


def main():
    train = [r for name, spec in DOMAINS.items() for r in rows_for_domain(name, spec)]
    boundary = best_linear_boundary(train)
    tests = []
    for name, spec in UNSEEN.items():
        rows = rows_for_domain(name, spec)
        tests.append({"domain": name, "result": evaluate(rows, boundary)})
    print(json.dumps({
        "training_domains": list(DOMAINS),
        "boundary": boundary,
        "unseen": tests,
        "all_unseen_perfect": all(t["result"]["accuracy"] == 1.0 for t in tests),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
