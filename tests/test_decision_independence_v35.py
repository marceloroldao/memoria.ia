from memoria_resolutiva.decision_independence import DecisionIndependentConceptMemory


def build_similar():
    m = DecisionIndependentConceptMemory()
    for epoch, ctx in enumerate([
        {"credito", "cliente", "conta"},
        {"emprestimo", "cliente", "conta"},
        {"credito", "juros", "cliente"},
    ], start=1):
        m.observe(epoch, "tarifa", ctx)
        m.observe(epoch, "cobranca", ctx | {"mensal"})
    return m


def test_repeating_decision_does_not_change_confidence():
    m = build_similar()
    a = m.decide(3, "tarifa", "cobranca")
    b = m.decide(3, "tarifa", "cobranca")
    assert a.merge_confidence == b.merge_confidence


def test_decisions_do_not_mutate_raw_observations():
    m = build_similar()
    before = m.observations()
    m.decide(3, "tarifa", "cobranca")
    m.decide(3, "tarifa", "cobranca")
    assert m.observations() == before


def test_new_raw_divergent_evidence_can_reduce_merge_confidence():
    m = build_similar()
    before = m.raw_merge_confidence("tarifa", "cobranca", upto_epoch=3)
    m.observe(4, "tarifa", {"tributo", "governo", "regulacao"})
    m.observe(4, "cobranca", {"fatura", "cliente", "pagamento"})
    m.observe(5, "tarifa", {"imposto", "setor", "regra"})
    m.observe(5, "cobranca", {"boleto", "servico", "pagamento"})
    after = m.raw_merge_confidence("tarifa", "cobranca", upto_epoch=5)
    assert after < before


def test_history_records_beliefs_not_evidence():
    m = build_similar()
    m.decide(2, "tarifa", "cobranca")
    m.decide(3, "tarifa", "cobranca")
    history = m.decision_history("tarifa", "cobranca")
    assert len(history) == 2
    assert len(m.observations()) == 6
