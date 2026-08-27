from __future__ import annotations

import json
import random
import time
from collections import Counter

from memoria_resolutiva.semantic_router_v96 import AdaptiveSemanticRouterV96, SemanticRouterV96
from memoria_resolutiva.textual import native_context_available

CONCEPTS = 5000
CLEAR_QUERIES = 950
AMBIGUOUS_QUERIES = 50

NATURAL_CORPUS = [
    "o carro ficou parado na estrada depois de uma falha no motor",
    "o automovel precisou de oficina depois que o motor aqueceu",
    "o veiculo entrou na garagem para manutencao e troca de oleo",
    "o cachorro correu pelo quintal e latiu perto da casa",
    "o cao dormiu ao lado da porta depois de brincar no quintal",
    "o animal domestico recebeu comida e agua perto da casa",
    "a internet caiu quando a fibra perdeu sinal no roteador",
    "o link de fibra voltou depois que o tecnico reiniciou o roteador",
    "a conexao de rede ficou instavel durante a falha do provedor",
    "o pagamento do boleto foi confirmado pelo banco durante a tarde",
    "a fatura foi quitada depois que o cliente pagou o boleto",
    "o banco registrou o pagamento e atualizou o saldo da conta",
    "o banco de madeira ficou na praca ao lado da arvore",
    "as pessoas sentaram no banco da praca durante a caminhada",
    "o marceneiro consertou o banco de madeira usado como assento",
] * 12

NATURAL_CONCEPTS = {
    "veiculo": {"carro", "veiculo"},
    "animal": {"cachorro", "animal"},
    "conectividade": {"internet", "rede"},
    "financeiro": {"pagamento", "fatura"},
    "mobiliario": {"assento", "madeira"},
}

PHRASE_PROBES = [
    "automovel na oficina",
    "cao no quintal",
    "fibra sem sinal",
    "boleto para pagamento",
    "banco usado como assento",
    "banco confirmou a fatura",
    "madeira do banco na praca",
    "pagamento da fatura no banco",
]


def build_corpus(n: int):
    sentences = []
    anchors = {}
    for i in range(n):
        cid = f"c{i:05d}"
        anchor = f"anchor{i}"
        anchors[cid] = (anchor,)
        family = f"family{i % 251}"
        domain = f"domain{i % 97}"
        sentences.extend([
            f"query{i} {anchor} rare{i} {family} {domain} shared system context",
            f"{anchor} query{i} rare{i} {family} {domain} shared system context",
        ])
    return sentences, anchors


def build(router_cls, sentences, anchors):
    router = router_cls(threshold=0.0, min_margin=0.0, use_native=True)
    router.observe(sentences)
    for cid, values in anchors.items():
        router.register_concept(cid, values)
    return router


def run_full(router, queries):
    t0 = time.perf_counter()
    out = [router.resolve_token(q) for q in queries]
    return time.perf_counter() - t0, out


def run_adaptive(router, queries):
    modes = Counter()
    out = []
    t0 = time.perf_counter()
    for q in queries:
        out.append(router.resolve_token(q))
        modes[router.last_route_mode] += 1
    return time.perf_counter() - t0, out, modes


def run_phrase_probe():
    full = SemanticRouterV96(threshold=0.0, min_margin=0.01, use_native=True)
    adaptive = AdaptiveSemanticRouterV96(
        threshold=0.0,
        min_margin=0.01,
        use_native=True,
        adaptive_threshold=4,
        candidate_limit=4,
    )
    for router in (full, adaptive):
        router.observe(NATURAL_CORPUS)
        for cid, anchors in NATURAL_CONCEPTS.items():
            router.register_concept(cid, anchors)

    t0 = time.perf_counter()
    expected = [full.resolve_text(text) for text in PHRASE_PROBES]
    full_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    actual = [adaptive.resolve_text(text) for text in PHRASE_PROBES]
    adaptive_s = time.perf_counter() - t0

    for a, b in zip(expected, actual):
        if a.concept_id != b.concept_id or abs(a.score-b.score) > 1e-12 or abs(a.margin-b.margin) > 1e-12:
            raise AssertionError((a, b))
    if any(item.concept_id is None for item in actual):
        raise AssertionError(actual)
    return full_s, adaptive_s


def main():
    if not native_context_available():
        raise SystemExit("native core unavailable")
    sentences, anchors = build_corpus(CONCEPTS)
    full = build(SemanticRouterV96, sentences, anchors)
    adaptive = AdaptiveSemanticRouterV96(
        threshold=0.0,
        min_margin=0.0,
        use_native=True,
        adaptive_threshold=512,
        candidate_limit=32,
    )
    adaptive.observe(sentences)
    for cid, values in anchors.items():
        adaptive.register_concept(cid, values)

    rng = random.Random(126)
    queries = [f"query{rng.randrange(CONCEPTS)}" for _ in range(CLEAR_QUERIES)]
    queries.extend(["shared", "system", "context", "family1", "domain1"] * (AMBIGUOUS_QUERIES // 5))
    rng.shuffle(queries)

    full_s, expected = run_full(full, queries)
    adaptive_s, actual, modes = run_adaptive(adaptive, queries)
    for a, b in zip(expected, actual):
        if a.concept_id != b.concept_id or abs(a.score-b.score) > 1e-12 or abs(a.margin-b.margin) > 1e-12:
            raise AssertionError((a, b))

    phrase_full_s, phrase_adaptive_s = run_phrase_probe()

    print(json.dumps({
        "concepts": CONCEPTS,
        "queries": len(queries),
        "clear_queries": CLEAR_QUERIES,
        "ambiguous_queries": AMBIGUOUS_QUERIES,
        "candidate_limit": 32,
        "full_query_s": full_s,
        "adaptive_query_s": adaptive_s,
        "effective_speedup": full_s / adaptive_s if adaptive_s else None,
        "route_modes": dict(sorted(modes.items())),
        "full_verify_fraction": modes.get("full_verify", 0) / len(queries),
        "phrase_queries": len(PHRASE_PROBES),
        "phrase_full_query_s": phrase_full_s,
        "phrase_adaptive_query_s": phrase_adaptive_s,
        "phrase_effective_speedup": phrase_full_s / phrase_adaptive_s if phrase_adaptive_s else None,
        "phrase_parity": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
