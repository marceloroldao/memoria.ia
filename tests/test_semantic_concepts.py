from memoria_resolutiva.semantic_concepts import SemanticConceptIndex, normalize_concept_surface


def test_registered_aliases_resolve_to_same_stable_concept():
    index = SemanticConceptIndex()
    concept = index.register_concept(
        "voltage",
        aliases=("potential difference", "DDP"),
        namespace="electronics",
    )

    assert index.resolve("voltage", namespace="electronics").concept_id == concept.concept_id
    assert index.resolve("potential difference", namespace="electronics").concept_id == concept.concept_id
    assert index.resolve("DDP", namespace="electronics").concept_id == concept.concept_id


def test_case_accent_punctuation_and_spacing_normalize_deterministically():
    assert normalize_concept_surface("  Diferença   de Potencial  ") == "diferenca de potencial"
    assert normalize_concept_surface("DIFERENÇA-de-potencial") == "diferenca de potencial"

    index = SemanticConceptIndex()
    concept = index.register_concept("Diferença de Potencial", namespace="electronics")
    resolved = index.resolve("diferença-de-potencial", namespace="electronics")
    assert resolved.status == "HIT"
    assert resolved.concept_id == concept.concept_id


def test_concept_id_is_deterministic_for_same_identity():
    first = SemanticConceptIndex().register_concept(
        "voltage", namespace="electronics", sense_key="electric potential"
    )
    second = SemanticConceptIndex().register_concept(
        "VOLTAGE", namespace="electronics", sense_key="electric-potential"
    )
    assert first.concept_id == second.concept_id


def test_alias_collision_preserves_polysemy_and_fails_closed():
    index = SemanticConceptIndex()
    finance = index.register_concept(
        "financial bank",
        aliases=("bank",),
        namespace="english",
        sense_key="finance",
    )
    geography = index.register_concept(
        "river bank",
        aliases=("bank",),
        namespace="english",
        sense_key="geography",
    )

    resolved = index.resolve("bank", namespace="english")
    assert resolved.status == "UNRESOLVED"
    assert resolved.reason == "ambiguous"
    assert set(resolved.candidate_ids) == {finance.concept_id, geography.concept_id}

    assert index.resolve("financial bank", namespace="english").concept_id == finance.concept_id
    assert index.resolve("river bank", namespace="english").concept_id == geography.concept_id


def test_namespace_isolation_prevents_alias_leakage():
    index = SemanticConceptIndex()
    concept = index.register_concept("voltage", aliases=("DDP",), namespace="profile:a")

    assert index.resolve("DDP", namespace="profile:a").concept_id == concept.concept_id
    other = index.resolve("DDP", namespace="profile:b")
    assert other.status == "UNRESOLVED"
    assert other.reason == "unknown"


def test_unknown_surface_is_not_fuzzy_guessed():
    index = SemanticConceptIndex()
    index.register_concept("voltage", aliases=("DDP",), namespace="electronics")

    resolved = index.resolve("electric tension", namespace="electronics")
    assert resolved.status == "UNRESOLVED"
    assert resolved.reason == "unknown"
    assert resolved.candidate_ids == ()


def test_empty_surface_fails_closed_without_candidates():
    index = SemanticConceptIndex()
    resolved = index.resolve(" --- ", namespace="electronics")
    assert resolved.status == "UNRESOLVED"
    assert resolved.reason == "empty"
    assert resolved.candidate_ids == ()


def test_re_registering_same_identity_adds_alias_without_changing_id():
    index = SemanticConceptIndex()
    first = index.register_concept("voltage", aliases=("DDP",), namespace="electronics")
    second = index.register_concept(
        "voltage",
        aliases=("potential difference",),
        namespace="electronics",
    )

    assert first.concept_id == second.concept_id
    assert index.resolve("DDP", namespace="electronics").concept_id == first.concept_id
    assert index.resolve("potential difference", namespace="electronics").concept_id == first.concept_id


def test_explicit_concept_id_cannot_be_reused_for_different_identity():
    index = SemanticConceptIndex()
    index.register_concept("voltage", concept_id="concept:shared", namespace="electronics")

    try:
        index.register_concept("current", concept_id="concept:shared", namespace="electronics")
    except ValueError as exc:
        assert "different concept identity" in str(exc)
    else:
        raise AssertionError("reusing an explicit concept ID for another identity must fail")
