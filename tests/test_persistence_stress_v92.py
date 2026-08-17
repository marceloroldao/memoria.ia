from pathlib import Path

from memoria_resolutiva.api_v90 import ResolutiveMemoryAPI


def build_api(concepts: int = 100, routes_per_concept: int = 4):
    m = ResolutiveMemoryAPI()
    routes = []
    for i in range(concepts):
        payload = {"concept": i, "facts": [i, i + 1, i + 2]}
        for r in range(routes_per_concept):
            route = ("scope" if r % 2 else "private", f"agent-{r%3}", f"mod-{r%4}", f"k{i}")
            m.remember(f"k{i}", payload, route, modality=f"mod-{r%4}", provenance=f"agent-{r%3}")
            routes.append(route)
            for _ in range(24 + (r % 8)):
                m.reinforce(route)
        if i % 5 == 0:
            for _ in range(20):
                m.challenge(routes[-routes_per_concept])
    return m, routes


def signature(m, routes):
    out = []
    for route in routes:
        status = m.route_status(route)
        node = m.recall(route, include_inactive=True)
        out.append((route, node.knowledge_id if node else None, status.active_depth, status.historical_depth))
    return tuple(out)


def test_repeated_save_load_has_zero_state_drift(tmp_path: Path):
    m, routes = build_api(120, 4)
    baseline = signature(m, routes)
    path = tmp_path / "stress.snapshot"
    for _ in range(10):
        m.save(path)
        m = ResolutiveMemoryAPI.load(path)
        assert signature(m, routes) == baseline
    assert path.exists()
    assert path.stat().st_size > 0


def test_shared_payload_count_survives_restarts(tmp_path: Path):
    m, _ = build_api(50, 8)
    path = tmp_path / "shared.snapshot"
    for _ in range(5):
        m.save(path)
        m = ResolutiveMemoryAPI.load(path)
        assert m._memory.knowledge.knowledge_count == 50
        assert m._memory.knowledge.route_count == 400
