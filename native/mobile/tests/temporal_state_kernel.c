#include "temporal_state_kernel.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static int check_repeated_values(void) {
    const memoria_state_fact facts[] = {
        {"repeated", "sensor", "location", "oficina", 40, 1.0},
        {"old", "sensor", "location", "garagem", 10, 1.0},
        {"first", "sensor", "location", "oficina", 20, 1.0},
        {"unrelated", "other", "location", "deposito", 35, 1.0},
        {"middle", "sensor", "location", "oficina", 30, 1.0},
        {"old-conflict", "sensor", "location", "oficina", 10, 1.0},
        {"latest-conflict", "sensor", "location", "garagem", 40, 1.0},
    };
    memoria_temporal_state_result result = memoria_temporal_state_resolve("sensor", "location", facts, 1);
    CHECK(result.hit && !result.transition_detected && result.previous_memory_id == NULL);

    result = memoria_temporal_state_resolve("sensor", "location", facts, 5);
    CHECK(result.hit && result.transition_detected);
    CHECK(strcmp(result.current_memory_id, "repeated") == 0);
    CHECK(strcmp(result.previous_memory_id, "old") == 0);

    result = memoria_temporal_state_resolve("sensor", "location", facts, 6);
    CHECK(result.hit && !result.transition_detected && result.previous_memory_id == NULL);
    CHECK(strcmp(result.current_memory_id, "repeated") == 0);

    result = memoria_temporal_state_resolve("sensor", "location", facts, 7);
    CHECK(!result.hit);
    return 0;
}

int main(void) {
    memoria_state_fact facts[] = {
        {"m1","device-alpha","finish","matte",1,1.0},
        {"m2","device-beta","finish","gloss",2,1.0},
        {"m3","device-alpha","voltage","12v",3,1.0},
        {"m4","device-alpha","finish","satin",4,1.0},
        {"m5","device-alpha","finish","polished",7,0.9}
    };
    memoria_temporal_state_result r;

    r = memoria_temporal_state_resolve("device-alpha","finish",facts,5);
    CHECK(r.hit == 1);
    CHECK(r.transition_detected == 1);
    CHECK(strcmp(r.previous_memory_id,"m4") == 0);
    CHECK(strcmp(r.current_memory_id,"m5") == 0);
    CHECK(strcmp(r.previous_value,"satin") == 0);
    CHECK(strcmp(r.current_value,"polished") == 0);
    CHECK(r.previous_order == 4);
    CHECK(r.current_order == 7);

    r = memoria_temporal_state_resolve("device-alpha","voltage",facts,5);
    CHECK(r.hit == 1);
    CHECK(r.transition_detected == 0);
    CHECK(r.previous_memory_id == NULL);
    CHECK(strcmp(r.current_value,"12v") == 0);

    r = memoria_temporal_state_resolve("device-beta","finish",facts,5);
    CHECK(r.hit == 1);
    CHECK(r.transition_detected == 0);
    CHECK(strcmp(r.current_memory_id,"m2") == 0);

    r = memoria_temporal_state_resolve("unknown","finish",facts,5);
    CHECK(r.hit == 0);
    CHECK(check_repeated_values() == 0);

    return 0;
}
