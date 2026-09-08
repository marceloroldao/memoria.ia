from __future__ import annotations

from memoria_resolutiva.topological_memory import AddressSpace
from memoria_resolutiva.topological_metrics import growth_profile, profile_word


def _stress_corpus() -> list[str]:
    corpus = []
    for index in range(1, 41):
        corpus.append(f"o sensor de sala {index} e o sensor de corredor {index}")
        corpus.append(f"a leitura de temperatura {index} para o servidor e para o painel")
        corpus.append(f"o estado que veio de origem {index} e que segue para destino {index}")
    corpus.extend(
        [
            "meu gato Alt dormiu no sofá",
            "o identificador raro XQZ91 apareceu uma vez",
        ]
    )
    return corpus


def test_dense_function_words_expose_hub_pressure_without_ranking_formula():
    addresses = AddressSpace()
    for text in _stress_corpus():
        addresses.ingest_text(text)

    de = profile_word(addresses, "de")
    para = profile_word(addresses, "para")
    que = profile_word(addresses, "que")
    e = profile_word(addresses, "e")
    o = profile_word(addresses, "o")
    alt = profile_word(addresses, "alt")
    rare = profile_word(addresses, "xqz91")

    assert all(profile is not None for profile in (de, para, que, e, o, alt, rare))
    assert de is not None and para is not None and que is not None and e is not None and o is not None
    assert alt is not None and rare is not None

    # Dense words must empirically accumulate more occurrences and phrase parents.
    # No ranking/selectivity formula is encoded here; these are raw topology facts.
    for hub in (de, para, que, e, o):
        assert hub.occurrences > alt.occurrences
        assert hub.phrase_parent_count > alt.phrase_parent_count
        assert hub.total_degree >= hub.phrase_parent_count

    assert alt.occurrences == 1
    assert rare.occurrences == 1
    assert alt.phrase_parent_count == 1
    assert rare.phrase_parent_count == 1


def test_repeated_language_reuses_nodes_and_reduces_new_node_growth():
    addresses = AddressSpace()
    new_nodes: list[int] = []
    reused_nodes: list[int] = []

    repeated = "o sensor de sala e o sensor de corredor"
    for _ in range(20):
        result = addresses.ingest_text(repeated)
        new_nodes.append(result.new_nodes)
        reused_nodes.append(result.reused_nodes)

    growth = growth_profile(new_nodes, reused_nodes)
    metrics = addresses.metrics()

    assert new_nodes[0] > 0
    assert all(value == 0 for value in new_nodes[1:])
    assert growth.average_reused_nodes_per_ingestion > growth.average_new_nodes_per_ingestion
    assert metrics["node_reuse_ratio"] > 0.8
    assert metrics["duplicate_address_count"] == 0


def test_hub_measurements_are_domain_independent():
    addresses = AddressSpace()
    corpus = [
        "o carro de joao e o carro de maria",
        "o pacote de rede e o pacote de controle",
        "o braço de robo e o braço de suporte",
        "o gato de ana e o gato de bia",
        "o sensor de pressão e o sensor de temperatura",
    ]
    for text in corpus:
        addresses.ingest_text(text)

    de = profile_word(addresses, "de")
    e = profile_word(addresses, "e")
    assert de is not None and e is not None
    assert de.phrase_parent_count == len(corpus)
    assert e.phrase_parent_count == len(corpus)
    assert de.occurrences == 10
    assert e.occurrences == 5
