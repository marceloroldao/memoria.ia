from memoria_resolutiva.contrastive_sentence_router_v96 import ContrastiveSentenceSemanticRouterV96


def build():
    r = ContrastiveSentenceSemanticRouterV96(
        threshold=0.07,
        min_margin=0.02,
        min_contrast_margin=0.02,
    )
    r.observe_concept("payment_delay", [
        "a mensalidade venceu e permanece sem pagamento",
        "a fatura esta atrasada e existe pendencia financeira",
        "o pagamento continua em aberto depois do vencimento",
    ])
    r.observe_concept("account_block", [
        "a conta do assinante foi suspensa e o acesso ficou bloqueado",
        "o cadastro esta restrito e a autenticacao foi negada",
        "o usuario permanece suspenso e nao consegue autenticar",
    ])
    return r


def test_counterexample_can_reject_completed_payment_without_erasing_delay_memory():
    r = build()
    assert r.resolve("a mensalidade nao foi paga e ja venceu").concept_id == "payment_delay"
    r.observe_counterexamples("payment_delay", [
        "o pagamento foi realizado e existe comprovante de quitacao",
        "a fatura ja foi paga e o recibo confirma a quitacao",
    ])
    assert r.resolve("foi emitido comprovante de pagamento ja realizado").concept_id is None
    assert r.resolve("a mensalidade nao foi paga e ja venceu").concept_id == "payment_delay"


def test_counterexample_can_reject_profile_update_from_account_block():
    r = build()
    r.observe_counterexamples("account_block", [
        "o usuario atualizou telefone e email no cadastro",
        "houve alteracao cadastral sem bloqueio de autenticacao",
    ])
    assert r.resolve("o usuario quer atualizar telefone e email do cadastro").concept_id is None
    assert r.resolve("o cadastro esta suspenso e o acesso foi negado").concept_id == "account_block"


def test_unknown_concept_counterexample_is_rejected():
    r = build()
    try:
        r.observe_counterexamples("missing", ["qualquer exemplo"])
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")
