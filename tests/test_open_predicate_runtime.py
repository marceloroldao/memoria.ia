from memoria_resolutiva.product_chat import _query_predicate_terms, _rank_relational_context


def test_query_predicate_terms_are_open_vocabulary():
    assert "tensão" in _query_predicate_terms("Qual é a tensão da minha bateria?", target="bateria")
    assert "temperatura" in _query_predicate_terms("Qual é a temperatura do meu sensor?", target="sensor")
    assert "fabricante" in _query_predicate_terms("Qual é o fabricante do meu inversor?", target="inversor")
    assert "versão" in _query_predicate_terms("Qual é a versão do meu firmware?", target="firmware")
    assert "porta" in _query_predicate_terms("Qual é a porta do meu serviço?", target="serviço")


def test_compatibility_synonyms_expand_without_defining_attribute_universe():
    predicates = _query_predicate_terms("Qual é o endereço do meu roteador?", target="roteador")
    assert "endereço" in predicates
    assert "ip" in predicates
    assert "address" in predicates


def test_open_predicate_ranking_prefers_voltage_edge_for_battery():
    ranked = _rank_relational_context(
        "Qual é a tensão da minha bateria?",
        (
            "bateria | is | principal\n"
            "principal | is | bateria\n"
            "principal | fabricante | Acme\n"
            "principal | potência | 500W\n"
            "principal | tensão | 48V\n"
            "reserva | is | bateria\n"
            "reserva | tensão | 24V"
        ),
    ).splitlines()

    assert set(ranked[:3]) == {
        "bateria | is | principal",
        "principal | is | bateria",
        "principal | tensão | 48V",
    }
    assert ranked.index("principal | tensão | 48V") < ranked.index("principal | fabricante | Acme")
    assert ranked.index("principal | tensão | 48V") < ranked.index("principal | potência | 500W")


def test_open_predicate_ranking_prefers_temperature_edge_for_sensor():
    ranked = _rank_relational_context(
        "Qual é a temperatura do meu sensor?",
        (
            "sensor | is | DHT22\n"
            "DHT22 | is | sensor\n"
            "DHT22 | fabricante | Aosong\n"
            "DHT22 | temperatura | 23.4C\n"
            "BMP280 | is | sensor\n"
            "BMP280 | temperatura | 22.8C"
        ),
    ).splitlines()

    assert set(ranked[:3]) == {
        "sensor | is | DHT22",
        "DHT22 | is | sensor",
        "DHT22 | temperatura | 23.4C",
    }
    assert ranked.index("DHT22 | temperatura | 23.4C") < ranked.index("DHT22 | fabricante | Aosong")


def test_open_predicate_ranking_prefers_fabricante_without_alias_entry():
    ranked = _rank_relational_context(
        "Qual é o fabricante do meu inversor?",
        (
            "inversor | is | INV01\n"
            "INV01 | is | inversor\n"
            "INV01 | potência | 5kW\n"
            "INV01 | fabricante | WEG\n"
            "INV02 | is | inversor\n"
            "INV02 | fabricante | SMA"
        ),
    ).splitlines()

    assert set(ranked[:3]) == {
        "inversor | is | INV01",
        "INV01 | is | inversor",
        "INV01 | fabricante | WEG",
    }
    assert ranked.index("INV01 | fabricante | WEG") < ranked.index("INV01 | potência | 5kW")
