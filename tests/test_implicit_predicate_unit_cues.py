from memoria_resolutiva.product_chat import _query_predicate_terms, _rank_relational_context


def test_volts_require_graph_cue_before_voltage_predicate_is_prioritized():
    context = (
        "bateria | is | principal\n"
        "principal | corrente | 20 A\n"
        "principal | tensão | 48 V\n"
        "reserva | tensão | 12 V"
    )

    without_graph = _rank_relational_context(
        "Com quantos volts está minha bateria?",
        context,
    ).splitlines()
    assert without_graph[0] == "bateria | is | principal"
    assert without_graph.index("principal | corrente | 20 A") < without_graph.index("principal | tensão | 48 V")

    with_graph = _rank_relational_context(
        "Com quantos volts está minha bateria?",
        context,
        graph_predicates=("tensão",),
    ).splitlines()
    assert with_graph.index("principal | tensão | 48 V") < with_graph.index("principal | corrente | 20 A")
    assert with_graph.index("principal | tensão | 48 V") < with_graph.index("reserva | tensão | 12 V")


def test_celsius_temperature_priority_comes_from_graph_cue():
    ranked = _rank_relational_context(
        "Qual a leitura em Celsius do meu sensor?",
        (
            "sensor | is | DHT22\n"
            "DHT22 | umidade | 45%\n"
            "DHT22 | temperatura | 24 C\n"
            "BMP280 | temperatura | 23 C"
        ),
        graph_predicates=("temperatura",),
    )
    lines = ranked.splitlines()
    assert lines[0] == "sensor | is | DHT22"
    assert lines.index("DHT22 | temperatura | 24 C") < lines.index("DHT22 | umidade | 45%")
    assert lines.index("DHT22 | temperatura | 24 C") < lines.index("BMP280 | temperatura | 23 C")


def test_amperes_current_priority_comes_from_graph_cue():
    ranked = _rank_relational_context(
        "Com quantos amperes trabalha meu motor?",
        (
            "motor | is | M1\n"
            "M1 | potencia | 2 kW\n"
            "M1 | corrente | 12 A\n"
            "M2 | corrente | 8 A"
        ),
        graph_predicates=("corrente",),
    )
    lines = ranked.splitlines()
    assert lines[0] == "motor | is | M1"
    assert lines.index("M1 | corrente | 12 A") < lines.index("M1 | potencia | 2 kW")
    assert lines.index("M1 | corrente | 12 A") < lines.index("M2 | corrente | 8 A")


def test_ranker_has_no_hidden_unit_mapping_without_graph_terms():
    terms = _query_predicate_terms("Com quantos volts está minha bateria?", target="bateria")
    assert "tensão" not in terms
    assert "tensao" not in terms

    symbol_terms = _query_predicate_terms("A bateria está em V?", target="bateria")
    assert "tensão" not in symbol_terms
    assert "tensao" not in symbol_terms
