#include "trajectory_json_adapter.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

int main(void) {
    memoria_semantic_source sources[] = {
        {"alpha", "alpha controller model is AX7", 1.0, 1, "user_assertion", "alpha"},
        {"beta", "beta controller model is BQ4", 1.0, 2, "user_assertion", "beta"}
    };
    memoria_trajectory_result r;
    size_t count = 0;
    int mode;

    mode = memoria_trajectory_resolve_json(
        "{\"query\":\"and that model?\",\"session_id\":\"s1\",\"conversation_window\":[{\"session_id\":\"s1\",\"role\":\"user\",\"text\":\"tell me about the alpha controller\",\"order\":1}]}",
        "and that model?", sources, 2, &r, &count);
    CHECK(mode == 1);
    CHECK(count == 1);
    CHECK(r.hit == 1);
    CHECK(r.used_window == 1);
    CHECK(strcmp(r.memory_id, "alpha") == 0);

    mode = memoria_trajectory_resolve_json(
        "{\"query\":\"and that model?\",\"session_id\":\"s2\",\"conversation_window\":[{\"session_id\":\"s1\",\"role\":\"user\",\"text\":\"tell me about the alpha controller\",\"order\":1}]}",
        "and that model?", sources, 2, &r, &count);
    CHECK(mode == 1);
    CHECK(r.hit == 0);

    mode = memoria_trajectory_resolve_json(
        "{\"query\":\"alpha controller model\"}",
        "alpha controller model", sources, 2, &r, &count);
    CHECK(mode == 0);

    mode = memoria_trajectory_resolve_json(
        "{\"query\":\"x\",\"session_id\":\"s1\",\"conversation_window\":{}}",
        "x", sources, 2, &r, &count);
    CHECK(mode == -1);

    return 0;
}
