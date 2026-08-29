from pathlib import Path

p = Path("native/mobile/memoria_mobile.c")
text = p.read_text(encoding="utf-8")
anchor = '''static turn_row *find_turn(memoria_mobile_handle *h, const char *memory_id) {
    size_t i;
    if (!h || !memory_id) return NULL;
    for (i = 0; i < h->turn_count; ++i) if (h->turns[i].memory_id && strcmp(h->turns[i].memory_id, memory_id) == 0) return &h->turns[i];
    return NULL;
}
'''
addition = anchor + '''
static int turn_factual_active(memoria_mobile_handle *h, const turn_row *turn) {
    turn_row *root;
    if (!h || !turn || turn->superseded) return 0;
    if (!turn->ultimate_source_memory_id || !*turn->ultimate_source_memory_id) return 1;
    root = find_turn(h, turn->ultimate_source_memory_id);
    if (root && root->superseded) return 0;
    return 1;
}
'''
if anchor not in text:
    raise SystemExit("find_turn anchor not found")
text = text.replace(anchor, addition, 1)
old = "        if (h->turns[i].superseded) continue;\n"
new = "        if (!turn_factual_active(h, &h->turns[i])) continue;\n"
if old not in text:
    raise SystemExit("factual source filter anchor not found")
text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
