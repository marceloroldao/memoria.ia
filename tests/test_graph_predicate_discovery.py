"""Open-vocabulary predicate discovery regression tests.

These tests deliberately use predicates that are absent from the legacy
_QUERY_ATTRIBUTE_ALIASES table. They establish the behavioral baseline needed
before that compatibility table can be reduced or removed.
"""

import pytest

from memoria_resolutiva.product_chat import _rank_relational_context


@pytest.mark.parametrize(
    ("message", "context", "expected_edge", "distractor_edge"),
    [
        (
            "Qual é a tensão da minha bateria?",
            (
                "bateria | is | principal\n"
                "principal | fabricante | Moura\n"
                "principal | temperatura | 31C\n"
                "principal | tensão | 12.7V\n"
                "reserva | is | bateria\n"
                "reserva | tensão | 12.4V"
            ),
            "principal | tensão | 12.7V",
            "principal | fabricante | Moura",
        ),
        (
            "Qual é a temperatura do meu sensor?",
            (
                "sensor | is | DHT22\n"
                "DHT22 | fabricante | Aosong\n"
                "DHT22 | tensão | 3.3V\n"
                "DHT22 | temperatura | 26C\n"
                "BMP280 | is | sensor\n"
                "BMP280 | temperatura | 25C"
            ),
            "DHT22 | temperatura | 26C",
            "DHT22 | tensão | 3.3V",
        ),
        (
            "Qual é o fabricante do meu inversor?",
            (
                "inversor | is | INV01\n"
                "INV01 | tensão | 220V\n"
                "INV01 | potência | 5kW\n"
                "INV01 | fabricante | WEG\n"
                "INV02 | is | inversor\n"
                "INV02 | fabricante | ABB"
            ),
            "INV01 | fabricante | WEG",
            "INV01 | potência | 5kW",
        ),
    ],
)
def test_unknown_query_predicate_selects_requested_anchor_edge(
    message, context, expected_edge, distractor_edge
):
    ranked = _rank_relational_context(message, context)
    lines = ranked.splitlines()

    # The graph first identifies the user's entity and then discovers the
    # requested predicate directly from the question/edge vocabulary. No
    # domain-specific attribute registration is allowed for these predicates.
    assert lines[0].split(" | ", 2)[0:2] in (["inversor", "is"], ["sensor", "is"], ["bateria", "is"])
    assert lines.index(expected_edge) < lines.index(distractor_edge)


def test_open_vocabulary_predicate_does_not_drop_competing_evidence():
    context = (
        "bateria | is | principal\n"
        "principal | fabricante | Moura\n"
        "principal | temperatura | 31C\n"
        "principal | tensão | 12.7V\n"
        "reserva | is | bateria\n"
        "reserva | tensão | 12.4V"
    )
    ranked = _rank_relational_context("Qual é a tensão da minha bateria?", context)

    assert set(ranked.splitlines()) == set(context.splitlines())
    assert len(ranked.splitlines()) == len(context.splitlines())
