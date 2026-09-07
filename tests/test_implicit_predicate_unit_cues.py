from memoria_resolutiva.product_chat import _query_predicate_terms, _rank_relational_context


def test_volts_prioritize_voltage_predicate_without_word_tensao_in_query():
    ranked = _rank_relational_context(
        "Com quantos volts está minha bateria?",
        (
            "bateria | is | principal\n"
            "principal | corrente | 20 A\n"
            "principal | tensão | 48 V\n"
            "reserva | tensão | 12 V"
        ),
    )
    lines = ranked.splitlines()
    assert lines[0] == "bateria | is | principal"
    assert lines.index("principal | tensão | 48 V") < lines.index("principal | corrente | 20 A")
    assert lines.index("principal | tensão | 48 V") < lines.index("reserva | tensão | 12 V")


def test_celsius_prioritizes_temperature_over_other_sensor_measurements():
    ranked = _rank_relational_context(
        "Qual a leitura em Celsius do meu sensor?",
        (
            "sensor | is | DHT22\n"
            "DHT22 | umidade | 45%\n"
            "DHT22 | temperatura | 24 C\n"
            "BMP280 | temperatura | 23 C"
        ),
    )
    lines = ranked.splitlines()
    assert lines[0] == "sensor | is | DHT22"
    assert lines.index("DHT22 | temperatura | 24 C") < lines.index("DHT22 | umidade | 45%")
    assert lines.index("DHT22 | temperatura | 24 C") < lines.index("BMP280 | temperatura | 23 C")


def test_amperes_prioritize_current_over_power_for_same_motor():
    ranked = _rank_relational_context(
        "Com quantos amperes trabalha meu motor?",
        (
            "motor | is | M1\n"
            "M1 | potencia | 2 kW\n"
            "M1 | corrente | 12 A\n"
            "M2 | corrente | 8 A"
        ),
    )
    lines = ranked.splitlines()
    assert lines[0] == "motor | is | M1"
    assert lines.index("M1 | corrente | 12 A") < lines.index("M1 | potencia | 2 kW")
    assert lines.index("M1 | corrente | 12 A") < lines.index("M2 | corrente | 8 A")


def test_unit_cues_are_conservative_and_ignore_single_letter_symbols():
    terms = _query_predicate_terms("A bateria está em V?", target="bateria")
    assert "tensão" not in terms
    assert "tensao" not in terms
