from memoria_resolutiva.polysemy_stability import evaluate_polysemy_order_stability


FINANCE = [
    "banco aprovou credito cliente",
    "banco concedeu emprestimo cliente",
    "cliente abriu conta banco",
    "banco cobrou juros financiamento",
    "banco recebeu deposito cliente",
]
DATA = [
    "banco armazenou dados sistema",
    "banco recebeu registros aplicacao",
    "consulta acessou banco dados",
    "servidor gravou informacao banco",
    "banco possui tabelas registros",
]


def test_core_orders_preserve_finance_data_separation():
    summary = evaluate_polysemy_order_stability(FINANCE, DATA, shuffled_runs=0)
    assert all(run.separated for run in summary.runs)


def test_randomized_order_has_high_separation_rate():
    summary = evaluate_polysemy_order_stability(FINANCE, DATA, shuffled_runs=25, seed=123)
    assert summary.separation_rate >= 0.9


def test_order_changes_do_not_cause_unbounded_sense_explosion():
    summary = evaluate_polysemy_order_stability(FINANCE, DATA, shuffled_runs=25, seed=321)
    assert summary.median_sense_count <= 4.0
    assert max(run.sense_count for run in summary.runs) <= 6
