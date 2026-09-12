from memoria_resolutiva.causal_multiagent_live_gym_v2 import (
    CausalMultiAgentLiveGymV2,
    InteragentCausalProbe,
)
from memoria_resolutiva.live_infinita_adapter_v2 import make_live_request
from memoria_resolutiva.multiagent_live_gym_v2 import MultiAgentObservation


def _obs(agent: str, tick: int, action: str, actual: str):
    request = make_live_request(
        frame_id=f"{agent}:F{tick}",
        state_addresses=(f"{agent}:s0", f"{agent}:s1"),
        intervention_id=f"{agent}:I{tick}",
        intervention_address=action,
        candidates=(
            ("y", ("obs:y",), (f"{agent}:s0", "obs:y")),
            ("z", ("obs:z",), (f"{agent}:s0", "obs:z")),
        ),
        provenance="causal-multiagent-live-gym-v2",
    )
    return MultiAgentObservation(agent, request, actual)


def _probe():
    return InteragentCausalProbe(
        probe_id="A:X->B:Y",
        source_agent="A",
        source_intervention="action:x",
        target_agent="B",
        target_observation=("obs:y",),
    )


def test_recurrent_exposure_without_negative_control_is_discriminative():
    gym = CausalMultiAgentLiveGymV2()
    probe = _probe()
    for tick in (1, 2):
        result = gym.step_batch(
            tick_id=f"T{tick}",
            observations=(
                _obs("A", tick, "action:x", "z"),
                _obs("B", tick, "action:noop", "y"),
            ),
            probes=(probe,),
        )
    contrast = dict(result.contrasts)[probe.probe_id]
    assert contrast.supported is True
    assert contrast.discriminative is True
    assert contrast.reason == "exposure-specific-recurrence"


def test_target_seen_without_source_intervention_blocks_causal_promotion():
    gym = CausalMultiAgentLiveGymV2()
    probe = _probe()
    for tick in (1, 2):
        gym.step_batch(
            tick_id=f"E{tick}",
            observations=(
                _obs("A", tick, "action:x", "z"),
                _obs("B", tick, "action:noop", "y"),
            ),
            probes=(probe,),
        )
    result = gym.step_batch(
        tick_id="C1",
        observations=(
            _obs("A", 3, "action:other", "z"),
            _obs("B", 3, "action:noop", "y"),
        ),
        probes=(probe,),
    )
    contrast = dict(result.contrasts)[probe.probe_id]
    assert contrast.supported is False
    assert contrast.discriminative is False
    assert contrast.reason == "target-also-occurs-without-intervention"


def test_confounder_that_drives_y_with_and_without_x_is_rejected():
    gym = CausalMultiAgentLiveGymV2()
    probe = _probe()

    # During the first two ticks X and an unmodelled world condition coincide with Y.
    for tick in (1, 2):
        gym.step_batch(
            tick_id=f"E{tick}",
            observations=(
                _obs("A", tick, "action:x", "z"),
                _obs("B", tick, "action:world-condition", "y"),
            ),
            probes=(probe,),
        )

    # The world condition persists after X is removed. Y still appears, exposing the
    # confound: X is not sufficiently discriminative for Y.
    result = gym.step_batch(
        tick_id="C-world",
        observations=(
            _obs("A", 3, "action:other", "z"),
            _obs("B", 3, "action:world-condition", "y"),
        ),
        probes=(probe,),
    )
    contrast = dict(result.contrasts)[probe.probe_id]
    assert contrast.supported is False
    assert contrast.reason == "target-also-occurs-without-intervention"


def test_missing_target_agent_is_not_counted_as_negative_control():
    gym = CausalMultiAgentLiveGymV2()
    probe = _probe()
    for tick in (1, 2):
        gym.step_batch(
            tick_id=f"E{tick}",
            observations=(
                _obs("A", tick, "action:x", "z"),
                _obs("B", tick, "action:noop", "y"),
            ),
            probes=(probe,),
        )
    result = gym.step_batch(
        tick_id="MISSING-B",
        observations=(_obs("A", 3, "action:other", "z"),),
        probes=(probe,),
    )
    contrast = dict(result.contrasts)[probe.probe_id]
    assert contrast.supported is True
    assert contrast.control_episodes == ()


def test_batch_order_does_not_change_contrast_evidence():
    probe = _probe()
    outputs = []
    for reverse in (False, True):
        gym = CausalMultiAgentLiveGymV2()
        for tick in (1, 2):
            batch = [
                _obs("A", tick, "action:x", "z"),
                _obs("B", tick, "action:noop", "y"),
            ]
            if reverse:
                batch.reverse()
            result = gym.step_batch(
                tick_id=f"T{tick}", observations=tuple(batch), probes=(probe,)
            )
        outputs.append((dict(result.contrasts)[probe.probe_id], gym.contrast_snapshot()))
    assert outputs[0] == outputs[1]
