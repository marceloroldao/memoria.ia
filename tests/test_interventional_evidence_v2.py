from memoria_resolutiva.interventional_evidence_v2 import InterventionalEvidenceMemory


def test_repeated_deliberate_application_supports_target():
    memory = InterventionalEvidenceMemory()
    for trial_id in ("A1", "A2"):
        memory.observe(
            trial_id=trial_id,
            context_signature=("ctx:a", "ctx:b"),
            intervention_address="act:x",
            intervention_applied=True,
            target_observation=("obs:y",),
        )
    result = memory.resolve(
        context_signature=("ctx:a", "ctx:b"),
        intervention_address="act:x",
        target_observation=("obs:y",),
    )
    assert result.supported is True
    assert result.reversible is False
    assert result.reason == "intervention-supported-without-withdrawal-evidence"


def test_withdrawal_without_target_strengthens_reversibility():
    memory = InterventionalEvidenceMemory()
    for trial_id in ("A1", "A2"):
        memory.observe(
            trial_id=trial_id,
            context_signature=("ctx:a",),
            intervention_address="act:x",
            intervention_applied=True,
            target_observation=("obs:y",),
        )
    memory.observe(
        trial_id="W1",
        context_signature=("ctx:a",),
        intervention_address="act:x",
        intervention_applied=False,
        target_observation=("obs:not-y",),
    )
    result = memory.resolve(
        context_signature=("ctx:a",),
        intervention_address="act:x",
        target_observation=("obs:y",),
    )
    assert result.supported is True
    assert result.reversible is True
    assert result.reason == "deliberate-intervention-with-withdrawal-contrast"


def test_target_persisting_without_intervention_blocks_promotion():
    memory = InterventionalEvidenceMemory()
    for trial_id in ("A1", "A2"):
        memory.observe(
            trial_id=trial_id,
            context_signature=("ctx:a",),
            intervention_address="act:x",
            intervention_applied=True,
            target_observation=("obs:y",),
        )
    memory.observe(
        trial_id="W1",
        context_signature=("ctx:a",),
        intervention_address="act:x",
        intervention_applied=False,
        target_observation=("obs:y",),
    )
    result = memory.resolve(
        context_signature=("ctx:a",),
        intervention_address="act:x",
        target_observation=("obs:y",),
    )
    assert result.supported is False
    assert result.reversible is False
    assert result.reason == "target-persists-without-intervention"


def test_other_context_does_not_contaminate_evidence():
    memory = InterventionalEvidenceMemory()
    for trial_id in ("A1", "A2"):
        memory.observe(
            trial_id=trial_id,
            context_signature=("ctx:a",),
            intervention_address="act:x",
            intervention_applied=True,
            target_observation=("obs:y",),
        )
    memory.observe(
        trial_id="W1",
        context_signature=("ctx:other",),
        intervention_address="act:x",
        intervention_applied=False,
        target_observation=("obs:y",),
    )
    result = memory.resolve(
        context_signature=("ctx:a",),
        intervention_address="act:x",
        target_observation=("obs:y",),
    )
    assert result.supported is True
    assert result.reason == "intervention-supported-without-withdrawal-evidence"


def test_restart_is_deterministic():
    memory = InterventionalEvidenceMemory()
    memory.observe(
        trial_id="A1",
        context_signature=("ctx:a",),
        intervention_address="act:x",
        intervention_applied=True,
        target_observation=("obs:y",),
    )
    restored = InterventionalEvidenceMemory.restore(memory.snapshot())
    assert restored.snapshot() == memory.snapshot()
