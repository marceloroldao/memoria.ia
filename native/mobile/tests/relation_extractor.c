#include "relation_extractor.h"
#include <assert.h>
#include <string.h>

int main(void) {
    memoria_relation rows[8];
    size_t n;

    n = memoria_extract_relations("server is atlas; laboratory is north", rows, 8);
    assert(n == 2);
    assert(strcmp(rows[0].subject, "server") == 0);
    assert(strcmp(rows[0].predicate, "is") == 0);
    assert(strcmp(rows[0].object, "atlas") == 0);
    assert(strcmp(rows[1].subject, "laboratory") == 0);
    assert(strcmp(rows[1].object, "north") == 0);

    n = memoria_extract_relations("sensor = active", rows, 8);
    assert(n == 1);
    assert(strcmp(rows[0].subject, "sensor") == 0);
    assert(strcmp(rows[0].object, "active") == 0);

    n = memoria_extract_relations("conversation without explicit relation", rows, 8);
    assert(n == 0);
    return 0;
}
