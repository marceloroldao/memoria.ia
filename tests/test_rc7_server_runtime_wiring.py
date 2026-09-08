from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SERVER = ROOT / "src" / "memoria_resolutiva" / "product_server.py"


def _server_source() -> str:
    return PRODUCT_SERVER.read_text(encoding="utf-8")


def test_rc7_chat_uses_semantic_wrapper_but_public_conversation_routes_do_not():
    source = _server_source()

    assert "chat_conversation_resolver = SemanticActivationConversationResolver(conversation_service)" in source
    assert "chat_service = _build_chat_service(service, configuration, conversation_resolver=chat_conversation_resolver)" in source
    assert "attach_conversation_routes(app, api_key=api_key, service=conversation_service)" in source
    assert "attach_conversation_routes(app, api_key=api_key, service=chat_conversation_resolver)" not in source


def test_rc7_storage_health_truthfully_exposes_semantic_chat_boundary():
    source = _server_source()

    assert '"semantic_chat_activation": True' in source
    assert '"semantic_chat_max_concepts": chat_conversation_resolver.max_concepts' in source
    assert '"conversation_runtime": "native" if conversation_is_native else "python"' in source
    assert '"episodic_runtime": "native" if episodic_is_native else "python"' in source


def test_rc7_server_keeps_conversation_runtime_switch_explicit_and_closed():
    source = _server_source()

    assert 'runtime = os.getenv("MEMORIA_CONVERSATION_RUNTIME", "native").strip().lower()' in source
    assert 'if runtime == "python":' in source
    assert 'if runtime != "native":' in source
    assert 'raise RuntimeError("MEMORIA_CONVERSATION_RUNTIME must be \'python\' or \'native\'")' in source


def test_rc7_server_keeps_episodic_runtime_switch_explicit_and_closed():
    source = _server_source()

    assert 'runtime = os.getenv("MEMORIA_EPISODIC_RUNTIME", "native").strip().lower()' in source
    assert 'if runtime == "python":' in source
    assert 'if runtime != "native":' in source
    assert 'raise RuntimeError("MEMORIA_EPISODIC_RUNTIME must be \'python\' or \'native\'")' in source


def test_rc7_native_shared_store_requires_both_native_runtimes():
    source = _server_source()

    assert 'if conversation_runtime != "native" or episodic_runtime != "native":' in source
    assert 'return None' in source
    assert 'return data_dir / "native-runtime"' in source
