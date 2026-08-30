#include "temporal_state_adapter.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

int main(void) {
    memoria_relation r1[1] = {{{0}}};
    memoria_relation r2[1] = {{{0}}};
    memoria_temporal_relation_source sources[2];
    memoria_state_fact facts[4];
    memoria_temporal_state_result result;
    size_t count;

    strcpy(r1[0].subject, "device mode");
    strcpy(r1[0].predicate, "is");
    strcpy(r1[0].object, "standby");
    r1[0].confidence = 0.95;

    strcpy(r2[0].subject, "device mode");
    strcpy(r2[0].predicate, "is");
    strcpy(r2[0].object, "active");
    r2[0].confidence = 0.95;

    sources[0].memory_id = "m1";
    sources[0].relations = r1;
    sources[0].relation_count = 1;
    sources[0].order = 10;
    sources[0].authority = 1.0;
    sources[1].memory_id = "m2";
    sources[1].relations = r2;
    sources[1].relation_count = 1;
    sources[1].order = 20;
    sources[1].authority = 1.0;

    count = memoria_temporal_build_facts(sources, 2, facts, 4);
    CHECK(count == 2);
    result = memoria_temporal_state_resolve("device mode", "is", facts, count);
    CHECK(result.hit);
    CHECK(result.transition_detected);
    CHECK(strcmp(result.previous_value, "standby") == 0);
    CHECK(strcmp(result.current_value, "active") == 0);
    CHECK(strcmp(result.previous_memory_id, "m1") == 0);
    CHECK(strcmp(result.current_memory_id, "m2") == 0);
    CHECK(result.previous_order == 10);
    CHECK(result.current_order == 20);
    return 0;
}
