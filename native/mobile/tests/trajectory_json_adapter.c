#include "trajectory_json_adapter.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

int main(void) {
    memoria_semantic_source sources[] = {
        {"m1","device alpha model is N7",1.0,1,"user_assertion","m1"},
        {"m2","device beta model is Q4",1.0,2,"user_assertion","m2"}
    };
    memoria_trajectory_result r;
    size_t count = 0;
    int rc;

    rc = memoria_trajectory_resolve_json(
        "{\"query\":\"and its model\",\"session_id\":\"s1\",\"conversation_window\":[{\"role\":\"user\",\"text\":\"we are discussing device alpha\",\"order\":1},{\"role\":\"assistant\",\"text\":\"device alpha is the cobalt unit\",\"order\":2}]}",
        "and its model", sources, 2, &r, &count);
    CHECK(rc == 1);
    CHECK(count == 2);
    CHECK(r.hit == 1);
    CHECK(strcmp(r.memory_id,"m1") == 0);
    CHECK(r.used_window == 1);

    rc = memoria_trajectory_resolve_json(
        "{\"query\":\"device beta model\"}",
        "device beta model", sources, 2, &r, &count);
    CHECK(rc == 0);

    rc = memoria_trajectory_resolve_json(
        "{\"query\":\"and its model\",\"session_id\":\"s2\",\"conversation_window\":[{\"session_id\":\"s1\",\"role\":\"user\",\"text\":\"device alpha\",\"order\":1}]}",
        "and its model", sources, 2, &r, &count);
    CHECK(rc == 1);
    CHECK(r.hit == 0);

    rc = memoria_trajectory_resolve_json(
        "{\"query\":\"x\",\"conversation_window\":{}}",
        "x", sources, 2, &r, &count);
    CHECK(rc == -1);
    return 0;
}
