from pathlib import Path
p = Path('native/mobile/memoria_mobile.c')
s = p.read_text()
old = '        sources[source_count].source_type = lineage.source_type;\n'
new = '        sources[source_count].source_type = h->turns[i].source_type;\n'
if old not in s:
    raise SystemExit('semantic source type anchor not found')
s = s.replace(old, new, 1)
p.write_text(s)
