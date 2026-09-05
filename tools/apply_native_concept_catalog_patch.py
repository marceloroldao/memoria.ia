from pathlib import Path

# Public ABI: additive symbol, ABI version remains 1.
p = Path('include/memoria_mobile.h')
s = p.read_text()
anchor = 'memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *handle);\n'
addition = '''memoria_mobile_status memoria_mobile_apply_concept_catalog_json(\n    memoria_mobile_handle *handle,\n    memoria_mobile_buffer request_json,\n    memoria_mobile_buffer *response_json\n);\n\n'''
if s.count(anchor) != 1:
    raise SystemExit('memoria_mobile.h flush anchor mismatch')
p.write_text(s.replace(anchor, addition + anchor, 1))

# BDR catalog persistence keeps fingerprint in the same durable batch.
Path('native/mobile/concept_identity_bdr.h').write_text('''#ifndef MEMORIA_CONCEPT_IDENTITY_BDR_H\n#define MEMORIA_CONCEPT_IDENTITY_BDR_H\n\n#include "concept_identity_state.h"\n\n#include <stddef.h>\n\ntypedef struct memoria_concept_bdr memoria_concept_bdr;\n\nint memoria_concept_bdr_open(\n    const char *data_dir,\n    const char *organization_id,\n    memoria_concept_bdr **out\n);\n\nint memoria_concept_bdr_save(\n    memoria_concept_bdr *store,\n    const memoria_concept_state_row *rows,\n    size_t row_count\n);\n\nint memoria_concept_bdr_save_catalog(\n    memoria_concept_bdr *store,\n    const memoria_concept_state_row *rows,\n    size_t row_count,\n    const char *fingerprint\n);\n\nint memoria_concept_bdr_load(\n    memoria_concept_bdr *store,\n    memoria_concept_state_row *rows,\n    size_t row_capacity,\n    size_t *row_count\n);\n\nint memoria_concept_bdr_load_fingerprint(\n    memoria_concept_bdr *store,\n    char *fingerprint,\n    size_t fingerprint_cap\n);\n\nint memoria_concept_bdr_sync(memoria_concept_bdr *store);\nvoid memoria_concept_bdr_close(memoria_concept_bdr *store);\n\n#endif\n''')

p = Path('native/mobile/concept_identity_bdr.c')
s = p.read_text()
start = s.index('int memoria_concept_bdr_save(')
end = s.index('int memoria_concept_bdr_load(', start)
replacement = r'''int memoria_concept_bdr_save_catalog(memoria_concept_bdr *store, const memoria_concept_state_row *rows, size_t row_count, const char *fingerprint) {
    size_t op_count = row_count + 3u, i;
    bdr_atomic_c_operation *ops;
    char (*keys)[KEY_CAP];
    char (*values)[ROW_CAP];
    char schema[32], count[32], suffix[64];
    bdr_atomic_c_batch_result result = {0};
    int ok = 0;
    if (!store || (row_count && !rows) || row_count > MEMORIA_CONCEPT_MAX_CONCEPTS || !fingerprint) return 0;
    ops = (bdr_atomic_c_operation *)calloc(op_count, sizeof(*ops));
    keys = (char (*)[KEY_CAP])calloc(op_count, sizeof(*keys));
    values = (char (*)[ROW_CAP])calloc(op_count, sizeof(*values));
    if (!ops || !keys || !values) goto done;
    snprintf(schema, sizeof(schema), "%u", CONCEPT_STATE_SCHEMA);
    snprintf(count, sizeof(count), "%zu", row_count);
    if (!make_key(store, keys[0], KEY_CAP, "meta/schema") ||
        !make_key(store, keys[1], KEY_CAP, "meta/count") ||
        !make_key(store, keys[2], KEY_CAP, "meta/fingerprint")) goto done;
    snprintf(values[0], ROW_CAP, "%s", schema);
    snprintf(values[1], ROW_CAP, "%s", count);
    snprintf(values[2], ROW_CAP, "%s", fingerprint);
    for (i = 0; i < 3u; ++i) {
        ops[i].type = BDR_ATOMIC_C_PUT;
        ops[i].key = keys[i]; ops[i].key_size = strlen(keys[i]);
        ops[i].value = values[i]; ops[i].value_size = strlen(values[i]);
    }
    for (i = 0; i < row_count; ++i) {
        snprintf(suffix, sizeof(suffix), "row/%06zu", i + 1u);
        if (!make_key(store, keys[i + 3u], KEY_CAP, suffix) || !serialize_row(&rows[i], values[i + 3u], ROW_CAP)) goto done;
        ops[i + 3u].type = BDR_ATOMIC_C_PUT;
        ops[i + 3u].key = keys[i + 3u]; ops[i + 3u].key_size = strlen(keys[i + 3u]);
        ops[i + 3u].value = values[i + 3u]; ops[i + 3u].value_size = strlen(values[i + 3u]);
    }
    ok = bdr_atomic_c_write_batch(store->db, ops, op_count, &result) == BDR_ATOMIC_C_OK &&
         result.durable == 1 && result.operations == op_count;
done:
    free(ops); free(keys); free(values);
    return ok;
}

int memoria_concept_bdr_save(memoria_concept_bdr *store, const memoria_concept_state_row *rows, size_t row_count) {
    return memoria_concept_bdr_save_catalog(store, rows, row_count, "");
}

int memoria_concept_bdr_load_fingerprint(memoria_concept_bdr *store, char *fingerprint, size_t fingerprint_cap) {
    char *text = NULL;
    size_t n = 0;
    if (!store || !fingerprint || fingerprint_cap == 0) return 0;
    fingerprint[0] = 0;
    if (!fetch_text(store, "meta/fingerprint", &text, &n)) return 0;
    if (!text) return 1;
    if (n >= fingerprint_cap) { free(text); return 0; }
    memcpy(fingerprint, text, n + 1u);
    free(text);
    return 1;
}

'''
p.write_text(s[:start] + replacement + s[end:])

# Runtime state: validate candidate index, durable write, then swap RAM state.
Path('native/mobile/concept_runtime_state.h').write_text('''#ifndef MEMORIA_CONCEPT_RUNTIME_STATE_H\n#define MEMORIA_CONCEPT_RUNTIME_STATE_H\n\n#include "concept_identity_bdr.h"\n#include "concept_identity_kernel.h"\n#include "concept_identity_state.h"\n\n#define MEMORIA_CONCEPT_FINGERPRINT_CAP 96u\n\ntypedef struct memoria_concept_runtime memoria_concept_runtime;\n\nint memoria_concept_runtime_open(\n    const char *data_dir,\n    const char *organization_id,\n    memoria_concept_runtime **out\n);\n\nconst memoria_concept_index *memoria_concept_runtime_index(const memoria_concept_runtime *runtime);\nconst char *memoria_concept_runtime_fingerprint(const memoria_concept_runtime *runtime);\nint memoria_concept_runtime_apply_catalog(\n    memoria_concept_runtime *runtime,\n    const memoria_concept_state_row *rows,\n    size_t row_count,\n    const char *fingerprint,\n    int *changed\n);\nint memoria_concept_runtime_sync(memoria_concept_runtime *runtime);\nvoid memoria_concept_runtime_close(memoria_concept_runtime *runtime);\n\n#endif\n''')

Path('native/mobile/concept_runtime_state.c').write_text(r'''#include "concept_runtime_state.h"

#include <stdlib.h>
#include <string.h>

struct memoria_concept_runtime {
    memoria_concept_bdr *store;
    memoria_concept_index index;
    char fingerprint[MEMORIA_CONCEPT_FINGERPRINT_CAP];
};

int memoria_concept_runtime_open(
    const char *data_dir,
    const char *organization_id,
    memoria_concept_runtime **out
) {
    memoria_concept_runtime *runtime;
    memoria_concept_state_row rows[MEMORIA_CONCEPT_MAX_CONCEPTS];
    size_t row_count = 0;
    if (!data_dir || !*data_dir || !organization_id || !*organization_id || !out) return 0;
    *out = NULL;
    runtime = (memoria_concept_runtime *)calloc(1, sizeof(*runtime));
    if (!runtime) return 0;
    memoria_concept_index_init(&runtime->index);
    if (!memoria_concept_bdr_open(data_dir, organization_id, &runtime->store) ||
        !memoria_concept_bdr_load(runtime->store, rows, MEMORIA_CONCEPT_MAX_CONCEPTS, &row_count) ||
        !memoria_concept_bdr_load_fingerprint(runtime->store, runtime->fingerprint, sizeof(runtime->fingerprint)) ||
        memoria_concept_state_import(&runtime->index, rows, row_count) != MEMORIA_CONCEPT_OK) {
        memoria_concept_runtime_close(runtime);
        return 0;
    }
    *out = runtime;
    return 1;
}

const memoria_concept_index *memoria_concept_runtime_index(const memoria_concept_runtime *runtime) {
    return runtime ? &runtime->index : NULL;
}

const char *memoria_concept_runtime_fingerprint(const memoria_concept_runtime *runtime) {
    return runtime ? runtime->fingerprint : "";
}

int memoria_concept_runtime_apply_catalog(
    memoria_concept_runtime *runtime,
    const memoria_concept_state_row *rows,
    size_t row_count,
    const char *fingerprint,
    int *changed
) {
    memoria_concept_index *candidate = NULL;
    memoria_concept_state_row *canonical_rows = NULL;
    size_t canonical_count = 0;
    int ok = 0;
    if (changed) *changed = 0;
    if (!runtime || !runtime->store || (!rows && row_count) || row_count > MEMORIA_CONCEPT_MAX_CONCEPTS ||
        !fingerprint || !fingerprint[0] || strlen(fingerprint) >= MEMORIA_CONCEPT_FINGERPRINT_CAP) return 0;
    if (strcmp(runtime->fingerprint, fingerprint) == 0) return 1;
    candidate = (memoria_concept_index *)calloc(1, sizeof(*candidate));
    canonical_rows = (memoria_concept_state_row *)calloc(MEMORIA_CONCEPT_MAX_CONCEPTS, sizeof(*canonical_rows));
    if (!candidate || !canonical_rows) goto done;
    memoria_concept_index_init(candidate);
    if (memoria_concept_state_import(candidate, rows, row_count) != MEMORIA_CONCEPT_OK) goto done;
    if (memoria_concept_state_export(candidate, canonical_rows, MEMORIA_CONCEPT_MAX_CONCEPTS, &canonical_count) != MEMORIA_CONCEPT_OK) goto done;
    if (!memoria_concept_bdr_save_catalog(runtime->store, canonical_rows, canonical_count, fingerprint)) goto done;
    if (!memoria_concept_bdr_sync(runtime->store)) goto done;
    runtime->index = *candidate;
    memcpy(runtime->fingerprint, fingerprint, strlen(fingerprint) + 1u);
    if (changed) *changed = 1;
    ok = 1;
done:
    free(candidate);
    free(canonical_rows);
    return ok;
}

int memoria_concept_runtime_sync(memoria_concept_runtime *runtime) {
    return runtime && runtime->store && memoria_concept_bdr_sync(runtime->store);
}

void memoria_concept_runtime_close(memoria_concept_runtime *runtime) {
    if (!runtime) return;
    memoria_concept_bdr_close(runtime->store);
    free(runtime);
}
''')

# Native mobile JSON bridge. Rows use byte-length-prefixed fields.
p = Path('native/mobile/memoria_mobile.c')
s = p.read_text()
flush_anchor = 'memoria_mobile_status memoria_mobile_flush(memoria_mobile_handle *h) {\n'
if s.count(flush_anchor) != 1:
    raise SystemExit('memoria_mobile.c flush anchor mismatch')
function = r'''static int concept_catalog_parse_number(const char **cursor, size_t *remaining, size_t *value) {
    size_t v = 0, digits = 0;
    const char *p;
    if (!cursor || !*cursor || !remaining || !value) return 0;
    p = *cursor;
    while (*remaining && *p >= '0' && *p <= '9') {
        if (v > ((size_t)-1 - (size_t)(*p - '0')) / 10u) return 0;
        v = v * 10u + (size_t)(*p - '0');
        ++p; --(*remaining); ++digits;
    }
    if (!digits || !*remaining || *p != ':') return 0;
    ++p; --(*remaining);
    *cursor = p;
    *value = v;
    return 1;
}

static int concept_catalog_parse_field(const char **cursor, size_t *remaining, char *dst, size_t cap) {
    size_t n;
    if (!concept_catalog_parse_number(cursor, remaining, &n) || n >= cap || n > *remaining) return 0;
    memcpy(dst, *cursor, n);
    dst[n] = 0;
    *cursor += n;
    *remaining -= n;
    return 1;
}

static int concept_catalog_decode_row(const char *wire, memoria_concept_state_row *row) {
    const char *cursor = wire;
    size_t remaining, count, i;
    if (!wire || !row) return 0;
    remaining = strlen(wire);
    memset(row, 0, sizeof(*row));
    if (!concept_catalog_parse_field(&cursor, &remaining, row->concept_id, sizeof(row->concept_id)) ||
        !concept_catalog_parse_field(&cursor, &remaining, row->namespace_name, sizeof(row->namespace_name)) ||
        !concept_catalog_parse_field(&cursor, &remaining, row->canonical, sizeof(row->canonical)) ||
        !concept_catalog_parse_field(&cursor, &remaining, row->sense_key, sizeof(row->sense_key)) ||
        !concept_catalog_parse_number(&cursor, &remaining, &count) || count > MEMORIA_CONCEPT_STATE_MAX_ALIASES_PER_CONCEPT) return 0;
    row->alias_count = count;
    for (i = 0; i < count; ++i)
        if (!concept_catalog_parse_field(&cursor, &remaining, row->aliases[i], sizeof(row->aliases[i]))) return 0;
    if (!concept_catalog_parse_number(&cursor, &remaining, &count) || count > MEMORIA_CONCEPT_MAX_CUES) return 0;
    row->context_cue_count = count;
    for (i = 0; i < count; ++i)
        if (!concept_catalog_parse_field(&cursor, &remaining, row->context_cues[i], sizeof(row->context_cues[i]))) return 0;
    return remaining == 0;
}

memoria_mobile_status memoria_mobile_apply_concept_catalog_json(
    memoria_mobile_handle *h,
    memoria_mobile_buffer request_json,
    memoria_mobile_buffer *response_json
) {
    char *json = NULL;
    char *fingerprint = NULL;
    char *wire_rows[MEMORIA_CONCEPT_MAX_CONCEPTS] = {0};
    memoria_concept_state_row *rows = NULL;
    size_t row_count = 0, i;
    long schema, expected_count;
    int changed = 0;
    memoria_mobile_status status = MEMORIA_MOBILE_INVALID_ARGUMENT;
    if (!h || !h->concept_runtime || !response_json) return MEMORIA_MOBILE_INVALID_ARGUMENT;
    response_json->data = NULL; response_json->size = 0;
    json = buffer_to_string(request_json);
    if (!json) goto done;
    schema = json_long(json, "schema", -1);
    expected_count = json_long(json, "concept_count", -1);
    fingerprint = json_string(json, "fingerprint");
    if (schema != 1 || expected_count < 0 || expected_count > (long)MEMORIA_CONCEPT_MAX_CONCEPTS ||
        !fingerprint || strlen(fingerprint) != 71u || strncmp(fingerprint, "sha256:", 7u) != 0 ||
        !strstr(json, "\"rows\"")) goto done;
    row_count = json_string_array(json, "rows", wire_rows, MEMORIA_CONCEPT_MAX_CONCEPTS);
    if ((long)row_count != expected_count) goto done;
    if (row_count) {
        rows = (memoria_concept_state_row *)calloc(row_count, sizeof(*rows));
        if (!rows) { status = MEMORIA_MOBILE_INTERNAL_ERROR; goto done; }
        for (i = 0; i < row_count; ++i)
            if (!concept_catalog_decode_row(wire_rows[i], &rows[i])) goto done;
    }
    if (!memoria_concept_runtime_apply_catalog(h->concept_runtime, rows, row_count, fingerprint, &changed)) {
        status = MEMORIA_MOBILE_PERSISTENCE_ERROR;
        goto done;
    }
    status = set_responsef(
        response_json,
        MEMORIA_MOBILE_OK,
        "{\"status\":\"OK\",\"changed\":%s,\"concept_count\":%zu,\"fingerprint\":\"%s\"}",
        changed ? "true" : "false", row_count, fingerprint
    );
done:
    free(rows);
    free_string_array(wire_rows, row_count);
    free(fingerprint);
    free(json);
    return status;
}

'''
p.write_text(s.replace(flush_anchor, function + flush_anchor, 1))

# Python binding: feature-detect the additive ABI-v1 symbol.
p = Path('src/memoria_resolutiva/native_runtime.py')
s = p.read_text()
anchor = '            function.restype = ctypes.c_int\n        self._lib.memoria_mobile_flush.argtypes = [ctypes.c_void_p]\n'
replacement = '''            function.restype = ctypes.c_int\n        optional_catalog_apply = getattr(self._lib, "memoria_mobile_apply_concept_catalog_json", None)\n        if optional_catalog_apply is not None:\n            optional_catalog_apply.argtypes = [ctypes.c_void_p, NativeBuffer, ctypes.POINTER(NativeBuffer)]\n            optional_catalog_apply.restype = ctypes.c_int\n        self._lib.memoria_mobile_flush.argtypes = [ctypes.c_void_p]\n'''
if s.count(anchor) != 1:
    raise SystemExit('native_runtime ABI anchor mismatch')
s = s.replace(anchor, replacement, 1)
anchor = '    @property\n    def closed(self) -> bool:\n        return self._closed\n\n'
addition = '''    def supports(self, function_name: str) -> bool:\n        return hasattr(self._lib, function_name)\n\n'''
if s.count(anchor) != 1:
    raise SystemExit('native_runtime closed anchor mismatch')
s = s.replace(anchor, anchor + addition, 1)
anchor = '    def flush(self) -> None:\n        if not self._released:\n            self.runtime.flush()\n\n'
addition = '''    def supports(self, function_name: str) -> bool:\n        if self._released:\n            return False\n        return self.runtime.supports(function_name)\n\n'''
if s.count(anchor) != 1:
    raise SystemExit('native_runtime lease flush anchor mismatch')
p.write_text(s.replace(anchor, anchor + addition, 1))

# Deterministic wire payload + synchronizer.
Path('src/memoria_resolutiva/native_concept_catalog.py').write_text('''from __future__ import annotations\n\nfrom dataclasses import dataclass\nimport hashlib\nimport json\n\nfrom .product_identity import MemoryScope\nfrom .semantic_concept_store import PersistentSemanticConceptStore\n\n\nNATIVE_CONCEPT_CATALOG_SCHEMA = 1\nNATIVE_CONCEPT_APPLY_SYMBOL = "memoria_mobile_apply_concept_catalog_json"\n\n\ndef _wire_field(value: object) -> str:\n    text = "" if value is None else str(value)\n    return f"{len(text.encode('utf-8'))}:{text}"\n\n\ndef _wire_row(row: dict[str, object]) -> str:\n    aliases = tuple(str(value) for value in row.get("aliases", ()))\n    cues = tuple(str(value) for value in row.get("context_cues", ()))\n    parts = [\n        _wire_field(row.get("concept_id")),\n        _wire_field(row.get("namespace")),\n        _wire_field(row.get("canonical")),\n        _wire_field(row.get("sense_key")),\n        f"{len(aliases)}:",\n    ]\n    parts.extend(_wire_field(value) for value in aliases)\n    parts.append(f"{len(cues)}:")\n    parts.extend(_wire_field(value) for value in cues)\n    return "".join(parts)\n\n\n@dataclass(frozen=True, slots=True)\nclass NativeConceptCatalog:\n    schema: int\n    namespace: str | None\n    concepts: tuple[dict[str, object], ...]\n    fingerprint: str\n\n    def payload(self) -> dict[str, object]:\n        return {\n            "schema": self.schema,\n            "namespace": self.namespace,\n            "concepts": [dict(row) for row in self.concepts],\n            "fingerprint": self.fingerprint,\n        }\n\n    def wire_payload(self) -> dict[str, object]:\n        return {\n            "schema": self.schema,\n            "namespace": self.namespace or "",\n            "fingerprint": self.fingerprint,\n            "concept_count": len(self.concepts),\n            "rows": [_wire_row(row) for row in self.concepts],\n        }\n\n\ndef build_native_concept_catalog(\n    store: PersistentSemanticConceptStore,\n    scope: MemoryScope,\n    *,\n    namespace: str | None,\n) -> NativeConceptCatalog:\n    concepts = store.list_concepts(scope, namespace=namespace)\n    rows: list[dict[str, object]] = []\n    for concept in concepts:\n        rows.append(\n            {\n                "concept_id": concept.concept_id,\n                "namespace": concept.namespace,\n                "canonical": concept.normalized_canonical,\n                "sense_key": concept.sense_key,\n                "aliases": list(concept.aliases),\n                "context_cues": list(concept.context_cues),\n            }\n        )\n    rows.sort(key=lambda row: str(row["concept_id"]))\n    material = {\n        "schema": NATIVE_CONCEPT_CATALOG_SCHEMA,\n        "namespace": namespace,\n        "concepts": rows,\n    }\n    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")\n    fingerprint = "sha256:" + hashlib.sha256(encoded).hexdigest()\n    return NativeConceptCatalog(\n        schema=NATIVE_CONCEPT_CATALOG_SCHEMA,\n        namespace=namespace,\n        concepts=tuple(rows),\n        fingerprint=fingerprint,\n    )\n\n\ndef apply_native_concept_catalog(runtime_lease, catalog: NativeConceptCatalog) -> bool:\n    supports = getattr(runtime_lease, "supports", None)\n    if supports is not None and not supports(NATIVE_CONCEPT_APPLY_SYMBOL):\n        raise RuntimeError("native Memoria.ia runtime does not support concept catalog materialization")\n    status, response = runtime_lease.call(NATIVE_CONCEPT_APPLY_SYMBOL, catalog.wire_payload())\n    if status != 0 or response.get("status") != "OK":\n        raise RuntimeError(f"native concept catalog materialization failed: status={status}")\n    if response.get("fingerprint") != catalog.fingerprint:\n        raise RuntimeError("native concept catalog materialization fingerprint mismatch")\n    if int(response.get("concept_count", -1)) != len(catalog.concepts):\n        raise RuntimeError("native concept catalog materialization count mismatch")\n    return bool(response.get("changed", False))\n''')

# Extend existing host lifecycle test to cover ABI apply, idempotence and restart.
p = Path('native/mobile/tests/concept_runtime_state.c')
s = p.read_text()
old = '    memoria_concept_runtime_close(runtime);\n    return 0;\n}\n'
addition = r'''    memoria_concept_runtime_close(runtime);
    runtime = NULL;

    /* Materialize a new authoritative catalog through the additive ABI. */
    {
        static const char *fp = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        static const char *request =
            "{\"schema\":1,\"namespace\":\"semantic\","
            "\"fingerprint\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\","
            "\"concept_count\":1,\"rows\":[\"12:concept:temp8:semantic11:temperature7:thermal2:11:temperature4:temp1:4:heat\"]}";
        memoria_mobile_buffer in = {(const uint8_t *)request, strlen(request)};
        memoria_mobile_buffer out = {0};
        assert(memoria_mobile_open(path, "org-runtime", &mobile) == MEMORIA_MOBILE_OK);
        assert(memoria_mobile_apply_concept_catalog_json(mobile, in, &out) == MEMORIA_MOBILE_OK);
        assert(out.data != NULL && strstr((const char *)out.data, "\"changed\":true") != NULL);
        memoria_mobile_free_buffer(out); out.data = NULL; out.size = 0;
        assert(memoria_mobile_apply_concept_catalog_json(mobile, in, &out) == MEMORIA_MOBILE_OK);
        assert(out.data != NULL && strstr((const char *)out.data, "\"changed\":false") != NULL);
        memoria_mobile_free_buffer(out);
        assert(memoria_mobile_flush(mobile) == MEMORIA_MOBILE_OK);
        memoria_mobile_close(mobile); mobile = NULL;

        assert(memoria_concept_runtime_open(path, "org-runtime", &runtime));
        assert(strcmp(memoria_concept_runtime_fingerprint(runtime), fp) == 0);
        index = memoria_concept_runtime_index(runtime);
        r = memoria_concept_resolve(index, "semantic", "temp");
        assert(r.status == MEMORIA_CONCEPT_HIT);
        assert(strcmp(r.concept_id, "concept:temp") == 0);
        memoria_concept_runtime_close(runtime);
    }
    return 0;
}
'''
if s.count(old) != 1:
    raise SystemExit('concept_runtime_state test tail mismatch')
p.write_text(s.replace(old, addition, 1))

# Python contract tests for UTF-8 byte lengths, feature detection and idempotent response.
Path('tests/test_native_concept_catalog_apply.py').write_text('''from __future__ import annotations\n\nimport pytest\n\nfrom memoria_resolutiva.native_concept_catalog import (\n    NATIVE_CONCEPT_APPLY_SYMBOL,\n    NativeConceptCatalog,\n    apply_native_concept_catalog,\n)\n\n\nclass _Lease:\n    def __init__(self, *, supported: bool = True, changed: bool = True):\n        self.supported = supported\n        self.changed = changed\n        self.calls: list[tuple[str, dict[str, object]]] = []\n\n    def supports(self, name: str) -> bool:\n        return self.supported and name == NATIVE_CONCEPT_APPLY_SYMBOL\n\n    def call(self, name: str, payload: dict[str, object]):\n        self.calls.append((name, payload))\n        return 0, {\n            "status": "OK",\n            "changed": self.changed,\n            "concept_count": payload["concept_count"],\n            "fingerprint": payload["fingerprint"],\n        }\n\n\ndef _catalog() -> NativeConceptCatalog:\n    return NativeConceptCatalog(\n        schema=1,\n        namespace="semantic",\n        concepts=(\n            {\n                "concept_id": "concept:voltage",\n                "namespace": "semantic",\n                "canonical": "tensão",\n                "sense_key": "eletrica",\n                "aliases": ["ddp", "diferença de potencial"],\n                "context_cues": ["circuito"],\n            },\n        ),\n        fingerprint="sha256:" + "a" * 64,\n    )\n\n\ndef test_wire_payload_uses_utf8_byte_lengths():\n    payload = _catalog().wire_payload()\n    row = payload["rows"][0]\n    assert isinstance(row, str)\n    assert "7:tensão" in row\n    assert "22:diferença de potencial" in row\n    assert payload["concept_count"] == 1\n\n\ndef test_apply_native_catalog_returns_changed_flag_and_exact_payload():\n    lease = _Lease(changed=True)\n    assert apply_native_concept_catalog(lease, _catalog()) is True\n    assert lease.calls[0][0] == NATIVE_CONCEPT_APPLY_SYMBOL\n    assert lease.calls[0][1]["fingerprint"] == _catalog().fingerprint\n\n\ndef test_apply_native_catalog_supports_idempotent_response():\n    assert apply_native_concept_catalog(_Lease(changed=False), _catalog()) is False\n\n\ndef test_apply_native_catalog_rejects_runtime_without_additive_symbol():\n    with pytest.raises(RuntimeError, match="does not support"):\n        apply_native_concept_catalog(_Lease(supported=False), _catalog())\n''')
