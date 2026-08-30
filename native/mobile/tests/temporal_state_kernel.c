#include "temporal_state_kernel.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

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

    return 0;
}
