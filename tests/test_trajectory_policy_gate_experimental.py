from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate


def build_gate():
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    gate.observe([
        "medico envia exame seguro hospital",
        "doutor transmite laudo cifrado clinica",
        "especialista remete imagem protegida laboratorio",
        "profissional envia registro privado centro",
        "centro recebe registro privado profissional",
        "hospital recebe exame seguro medico",
        "clinica recebe laudo cifrado doutor",
        "laboratorio recebe imagem protegida especialista",
    ])
    gate.register_role("source", ["medico", "doutor", "especialista"])
    gate.register_role("action", ["envia", "transmite", "remete"])
    gate.register_role("payload", ["exame", "laudo", "imagem"])
    gate.register_role("quality", ["seguro", "cifrado", "protegida"])
    gate.register_role("destination", ["hospital", "clinica", "laboratorio"])
    gate.register_pattern(("source", "action", "payload", "quality", "destination"))
    gate.register_pattern(("destination", "action", "payload", "quality", "source"))
    assert gate.calibrate()
    return gate


def test_gate_accepts_context_supported_valid_trajectory():
    gate = build_gate()
    result = gate.resolve("profissional recebe registro privado centro")
    assert result.decision == "accept"
    assert result.reason == "trajectory coverage accepted"


def test_gate_rejects_wrong_arity_with_supported_tokens():
    gate = build_gate()
    result = gate.resolve("profissional recebe registro privado")
    assert result.decision == "reject"
    assert result.reason == "trajectory arity mismatch"


def test_gate_fails_closed_for_absolute_open_set():
    gate = build_gate()
    result = gate.resolve("profissional recebe misterio privado centro")
    assert result.decision == "fail_closed"
    assert "absolute open-set" in result.reason


def test_gate_fails_closed_when_calibration_is_insufficient():
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    gate.observe(["fonte move dado destino", "destino move dado fonte"])
    gate.register_role("source", ["fonte"])
    gate.register_role("action", ["move"])
    gate.register_role("payload", ["dado"])
    gate.register_role("destination", ["destino"])
    gate.register_pattern(("source", "action", "payload", "destination"))
    assert not gate.calibrate()
    assert gate.resolve("fonte move dado destino").decision == "fail_closed"
