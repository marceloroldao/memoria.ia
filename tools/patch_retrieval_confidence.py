from pathlib import Path

p = Path('native/mobile/semantic_kernel.c')
s = p.read_text(encoding='utf-8')
old = '''        result.confidence = 0.28 + 0.26 * best_coverage + 0.24 * authority + 0.12 * (best_rank > 1.0 ? 1.0 : best_rank);\n        if (result.confidence > 0.9) result.confidence = 0.9;\n'''
new = '''        /* Keep the published/native response confidence contract stable.\n           Retrieval v2 changes candidate selection, not API semantics. */\n        result.confidence = 0.30 + 0.25 * best_coverage + 0.25 * authority;\n        if (result.confidence > 0.8) result.confidence = 0.8;\n'''
if old not in s:
    raise SystemExit('confidence anchor not found')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
