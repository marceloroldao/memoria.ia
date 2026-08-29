#include "relation_adapter.h"
#include "relation_extractor.h"

#include <assert.h>
#include <string.h>

int main(void) {
    memoria_relation relations[4];
    const char *ids[1] = {"rel1"};
    char json[1024];
    size_t n = memoria_extract_relations("sensor = active", relations, 4);
    assert(n == 1);

    /* Legacy/mobile wrapper keeps its original shape. */
    assert(memoria_relations_to_json(relations, n, "m1", json, sizeof(json)) == 1);
    assert(strstr(json, "\"subject\":\"sensor\"") != 0);
    assert(strstr(json, "\"predicate\":\"is\"") != 0);
    assert(strstr(json, "\"object\":\"active\"") != 0);
    assert(strstr(json, "\"source_memory_id\":\"m1\"") != 0);
    assert(strstr(json, "\"memory_id\":") == 0);

    /* Additive identity path exposes a stable relation memory id. */
    assert(memoria_relations_to_json_with_ids(relations, ids, n, "m1", json, sizeof(json)) == 1);
    assert(strstr(json, "\"memory_id\":\"rel1\"") != 0);
    assert(strstr(json, "\"source_memory_id\":\"m1\"") != 0);

    assert(memoria_relations_to_json(0, 0, "m2", json, sizeof(json)) == 1);
    assert(strcmp(json, "[]") == 0);
    return 0;
}
