from memoria_resolutiva.trajectory_contrastive_v96 import TrajectoryContrastiveRouterV96


def build():
    r = TrajectoryContrastiveRouterV96(
        threshold=0.14,
        min_margin=0.02,
        negative_threshold=0.20,
        min_contrast_margin=0.04,
    )
    r.observe_concept("payment_delay", [
        "a mensalidade venceu e permanece sem pagamento",
        "a fatura esta atrasada e existe pendencia financeira",
        "o pagamento continua em aberto apesar do prazo encerrado",
    ])
    r.observe_concept("optical_loss", [
        "a potencia optica recebida pela onu caiu abaixo do normal",
        "o enlace apresentou atenuacao elevada e sinal fraco",
        "a leitura optica mostrou perda de potencia na recepcao",
    ])
    r.observe_counterexample(
        "payment_delay",
        "foi emitido um comprovante de pagamento ja realizado",
    )
    r.observe_counterexample(
        "optical_loss",
        "o tecnico substituiu a fonte de alimentacao da onu",
    )
    return r


def test_counterexample_can_reject_related_open_set_case():
    r = build()
    out = r.resolve("o pagamento foi realizado e o cliente apresentou comprovante")
    assert out.concept_id is None
    assert out.source == "contrastive-reject"


def test_valid_payment_delay_remains_resolvable():
    r = build()
    out = r.resolve("a mensalidade ja venceu e continua sem pagamento")
    assert out.concept_id == "payment_delay"


def test_valid_optical_loss_remains_resolvable():
    r = build()
    out = r.resolve("a potencia optica da onu esta baixa e o sinal ficou fraco")
    assert out.concept_id == "optical_loss"
