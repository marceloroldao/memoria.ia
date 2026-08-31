from pathlib import Path

p = Path('native/mobile/memoria_mobile_post_v1.c')
s = p.read_text(encoding='utf-8')

anchor = '''static void external_request_free(external_request *r) {
    if (!r) return;
    free(r->content); free(r->namespace_id); free(r->source_url); free(r->source_domain);
    free(r->source_title); free(r->acquired_time); free(r->source_excerpt); free(r->provider_id);
    free(r->import_kind); free(r->request_id); free(r->session_id);
    free_string_array(r->parents, r->parent_count);
    memset(r, 0, sizeof(*r));
}
'''
helper = anchor + '''
/* The frozen v1 helper extracts JSON string bytes but deliberately does not
 * unescape them. External/public knowledge is fed by Android JSONObject, so
 * provenance values such as URLs may legally arrive with JSON escapes (for
 * example https:\\/\\/example.org). Decode the common JSON escapes before
 * validating or persisting the post-v1 external contract. */
static char *external_json_string(const char *json, const char *key) {
    char *value = json_string(json, key);
    char *read, *write;
    if (!value) return NULL;
    read = value;
    write = value;
    while (*read) {
        if (*read == '\\\\' && read[1]) {
            ++read;
            switch (*read) {
                case '\"': *write++ = '\"'; ++read; break;
                case '\\\\': *write++ = '\\\\'; ++read; break;
                case '/': *write++ = '/'; ++read; break;
                case 'n': *write++ = '\\n'; ++read; break;
                case 'r': *write++ = '\\r'; ++read; break;
                case 't': *write++ = '\\t'; ++read; break;
                case 'b': *write++ = '\\b'; ++read; break;
                case 'f': *write++ = '\\f'; ++read; break;
                default:
                    /* Preserve unsupported escapes (notably \\uXXXX) bytewise
                     * rather than silently corrupting public evidence. */
                    *write++ = '\\\\';
                    *write++ = *read++;
                    break;
            }
        } else {
            *write++ = *read++;
        }
    }
    *write = 0;
    return value;
}
'''
if anchor not in s:
    raise SystemExit('external_request_free anchor not found')
s = s.replace(anchor, helper, 1)

start = s.index('static int external_parse_request(')
end = s.index('\nstatic int external_fetch_field', start)
block = s[start:end]
block2 = block.replace('json_string(json, ', 'external_json_string(json, ')
if block == block2:
    raise SystemExit('no external parse json_string calls replaced')
s = s[:start] + block2 + s[end:]
p.write_text(s, encoding='utf-8')

# Add a native regression that mimics JSON escaped URL/quoted content from a
# consumer serializer. It must be accepted and persisted with decoded URL.
t = Path('native/mobile/tests/external_public_knowledge_mobile.c')
ts = t.read_text(encoding='utf-8')
needle = '''    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(inspect_external(h, public_id, &out) == MEMORIA_MOBILE_OK);
'''
insert = '''    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    /* Android/consumer serializers may escape forward slashes and quotes. */
    CHECK(external_learn(h,
        "{\\\"content\\\":\\\"android says \\\\\\\"ocean\\\\\\\" is public\\\","
        "\\\"source_class\\\":\\\"external_public\\\","
        "\\\"source_url\\\":\\\"https:\\\\/\\\\/example.org\\\\/android\\\","
        "\\\"source_domain\\\":\\\"example.org\\\",\\\"source_title\\\":\\\"Android \\\\\\\"Public\\\\\\\" Source\\\","
        "\\\"acquired_time\\\":\\\"2026-08-30T04:40:30Z\\\",\\\"import_kind\\\":\\\"imported\\\"}", &out) == MEMORIA_MOBILE_OK);
    CHECK(contains(out, "\\\"knowledge_class\\\":\\\"external_public\\\""));
    memoria_mobile_free_buffer(out); out = (memoria_mobile_buffer){0};

    CHECK(inspect_external(h, public_id, &out) == MEMORIA_MOBILE_OK);
'''
if needle not in ts:
    raise SystemExit('native test anchor not found')
ts = ts.replace(needle, insert, 1)
t.write_text(ts, encoding='utf-8')
