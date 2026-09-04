from pathlib import Path
p = Path('src/memoria_resolutiva/product_server.py')
s = p.read_text()
old = '''    automatic_semantic_consolidation = not conversation_is_native
    if automatic_semantic_consolidation:
        # Keep Python factual/provenance semantics out of native production startup.
        # Native consolidation is intentionally disabled until equivalent native
        # lineage and persistence behavior is implemented and parity-tested.
        from .conversation_semantic_bridge import AutoSemanticConsolidationConversationService

        conversation_service = AutoSemanticConsolidationConversationService(
            conversation_service,
            evidence_service,
        )
'''
new = '''    # Both runtimes now consolidate repeated factual claims automatically.
    # Python uses the bridge below; native performs the same operation internally
    # in the mobile/BDR runtime and therefore must not import Python provenance.
    automatic_semantic_consolidation = True
    if not conversation_is_native:
        from .conversation_semantic_bridge import AutoSemanticConsolidationConversationService

        conversation_service = AutoSemanticConsolidationConversationService(
            conversation_service,
            evidence_service,
        )
'''
if old not in s:
    raise SystemExit('semantic consolidation block not found')
p.write_text(s.replace(old,new,1))
