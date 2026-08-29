from pathlib import Path

path = Path("native/mobile/memoria_mobile.c")
text = path.read_text(encoding="utf-8")

include_needle = '#include "mobile_persistence.h"\n'
if include_needle not in text:
    raise SystemExit("mobile_persistence include not found")
if '#include "diagnostic_export.h"' not in text:
    text = text.replace(include_needle, include_needle + '#include "diagnostic_export.h"\n', 1)

needle = 'memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *h) {\n'
if text.count(needle) != 1:
    raise SystemExit(f"expected one flush function, found {text.count(needle)}")

block = r'''memoria_mobile_status memoria_mobile_export_snapshot_json(
    memoria_mobile_handle *h,
    memoria_mobile_buffer req,
    memoria_mobile_buffer *out
) {
    char *request = NULL;
    char *snapshot = NULL;
    long turn_offset, turn_limit, episode_offset, episode_limit;
    memoria_diagnostic_page page;
    memoria_mobile_status status;

    if (!h || !out) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (req.data && req.size) request = buffer_to_string(req);
    else request = dup_string("{}");
    if (!request) return MEMORIA_MOBILE_INTERNAL_ERROR;

    turn_offset = json_long(request, "turn_offset", 0);
    turn_limit = json_long(request, "turn_limit", 0);
    episode_offset = json_long(request, "episode_offset", 0);
    episode_limit = json_long(request, "episode_limit", 0);
    if (turn_offset < 0 || turn_limit < 0 || episode_offset < 0 || episode_limit < 0) {
        free(request);
        return MEMORIA_MOBILE_INVALID_ARGUMENT;
    }

    page.turn_offset = (size_t)turn_offset;
    page.turn_limit = (size_t)turn_limit;
    page.episode_offset = (size_t)episode_offset;
    page.episode_limit = (size_t)episode_limit;

    snapshot = memoria_diagnostic_export_json(
        h->organization_id,
        h->sequence,
        h->turns,
        h->turn_count,
        h->episodes,
        h->episode_count,
        page
    );
    free(request);
    if (!snapshot) return MEMORIA_MOBILE_INTERNAL_ERROR;
    status = set_response(out, snapshot, MEMORIA_MOBILE_OK);
    free(snapshot);
    return status;
}

memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *h) {
'''

text = text.replace(needle, block, 1)
path.write_text(text, encoding="utf-8")
