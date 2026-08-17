from memoria_resolutiva.routed_lifecycle import RoutedLifecycleMemory


def build_memory():
    m = RoutedLifecycleMemory(levels=5, max_strength=1.25)
    vision = ("private", "robot-1", "vision", "cup")
    language = ("collective", "fleet", "language", "cup")
    m.register("cup", {"class": "cup"}, vision, modality="vision", provenance="robot-1")
    m.register("cup", {"class": "cup"}, language, modality="language", provenance="fleet")
    return m, vision, language


def test_routes_share_payload_but_not_lifecycle_state():
    m, vision, language = build_memory()
    for _ in range(32):
        m.support(vision)
        m.support(language)
    assert m.resolve(vision).payload == m.resolve(language).payload
    for _ in range(24):
        m.contradict(vision)
    assert m.resolve(vision) is None
    assert m.resolve(language) is not None
    assert m.status(vision).historical_depth == 4
    assert m.status(language).active_depth == 4


def test_deactivated_route_can_reactivate_without_touching_other_route():
    m, vision, language = build_memory()
    for _ in range(32):
        m.support(vision)
        m.support(language)
    for _ in range(24):
        m.contradict(vision)
    before = m.status(language)
    for _ in range(16):
        m.support(vision)
    assert m.resolve(vision) is not None
    after = m.status(language)
    assert before == after


def test_inactive_route_can_still_be_inspected_historically():
    m, vision, _ = build_memory()
    for _ in range(32):
        m.support(vision)
    for _ in range(24):
        m.contradict(vision)
    assert m.resolve(vision) is None
    assert m.resolve(vision, require_active=False) is not None
