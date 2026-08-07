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


def test_evaluator_exposes_current_over_splitting_failure_surface():
    summary = evaluate_polysemy_order_stability(FINANCE, DATA, shuffled_runs=25, seed=321)
    # v0.30 deliberately records that the current local-Jaccard splitter creates
    # more than the two intended domain senses. Future versions should reduce
    # this number without losing finance/data separation.
    assert summary.median_sense_count >= 2.0
    assert max(run.sense_count for run in summary.runs) >= 2
