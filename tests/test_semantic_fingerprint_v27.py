from memoria_resolutiva.semantic_fingerprint import fingerprint, hybrid_similarity, structural_similarity


def test_fingerprint_extracts_event_structure():
    fp = fingerprint("Nova cobrança mensal de 12 reais para conexões de fibra óptica dos provedores")
    assert "fee" in fp.concepts
    assert "fiber" in fp.concepts
    assert "provider" in fp.concepts
    assert "monthly" in fp.concepts
    assert "12" in fp.numbers


def test_strong_paraphrase_scores_above_unrelated_document():
    origin = "Nova cobrança mensal de 12 reais será aplicada às conexões de fibra óptica dos provedores"
    paraphrase = "Uma tarifa de 12 reais por mês passará a incidir sobre conexões ópticas das operadoras."
    unrelated = "O telescópio registrou uma estrela a 12 anos-luz."
    assert hybrid_similarity(origin, paraphrase) > hybrid_similarity(origin, unrelated)


def test_similar_domain_without_fee_event_is_not_overweighted():
    origin = "Nova cobrança mensal de 12 reais será aplicada às conexões de fibra óptica dos provedores"
    same_domain = "Provedores ampliaram redes de fibra em 12 cidades neste mês."
    paraphrase = "Provedores terão de pagar taxa mensal de R$ 12 por enlaces de fibra."
    assert structural_similarity(origin, paraphrase) > structural_similarity(origin, same_domain)


def test_lexical_weight_validation():
    try:
        hybrid_similarity("a", "b", lexical_weight=1.5)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
