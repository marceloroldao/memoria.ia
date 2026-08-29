from pathlib import Path

p = Path("native/mobile/memoria_mobile.c")
text = p.read_text(encoding="utf-8")
old = '        if (session_id && strcmp(session_id, e->session_id ? e->session_id : "") != 0) continue;\n'
new = '        if (strcmp(session_id ? session_id : "", e->session_id ? e->session_id : "") != 0) continue;\n'
if old not in text:
    raise SystemExit("episode session filter anchor not found")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
