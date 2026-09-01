#include "composed_state_kernel.h"

#include <stdio.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"CHECK failed: %s (%s:%d)\n",#expr,__FILE__,__LINE__); return 1; } } while (0)

static int eq(const char *a, const char *b) {
    return a && b && strcmp(a, b) == 0;
}

int main(void) {
    const char *properties[] = {"model", "mode"};
    memoria_state_fact facts[] = {
        {"m-model-old", "device alpha", "model", "N6", 1, 0.90},
        {"m-mode-old", "device alpha", "mode", "idle", 2, 0.95},
        {"m-model-new", "device alpha", "model", "N7", 3, 0.85},
        {"m-other", "device beta", "mode", "active", 4, 1.00},
        {"m-mode-new", "device alpha", "mode", "active", 5, 0.92},
    };
    memoria_composed_state_result r;

    r = memoria_composed_state_resolve(
        "device alpha", properties, 2,
        facts, sizeof(facts) / sizeof(facts[0]));
    CHECK(r.hit == 1);
    CHECK(r.ambiguous == 0);
    CHECK(r.item_count == 2);
    CHECK(eq(r.entity, "device alpha"));
    CHECK(eq(r.items[0].property, "model"));
    CHECK(eq(r.items[0].value, "N7"));
    CHECK(eq(r.items[0].memory_id, "m-model-new"));
    CHECK(r.items[0].order == 3);
    CHECK(eq(r.items[1].property, "mode"));
    CHECK(eq(r.items[1].value, "active"));
    CHECK(eq(r.items[1].memory_id, "m-mode-new"));
    CHECK(r.items[1].order == 5);
    CHECK(r.confidence > 0.849 && r.confidence < 0.851);

    /* State composition is case-insensitive for entity/property matching. */
    {
        const char *case_props[] = {"MODEL"};
        r = memoria_composed_state_resolve(
            "DEVICE ALPHA", case_props, 1,
            facts, sizeof(facts) / sizeof(facts[0]));
        CHECK(r.hit == 1);
        CHECK(eq(r.items[0].value, "N7"));
        CHECK(eq(r.items[0].memory_id, "m-model-new"));
    }

    /* Missing requested evidence must not produce a partial/synthetic state. */
    {
        const char *missing[] = {"model", "firmware"};
        r = memoria_composed_state_resolve(
            "device alpha", missing, 2,
            facts, sizeof(facts) / sizeof(facts[0]));
        CHECK(r.hit == 0);
        CHECK(r.ambiguous == 1);
    }

    /* A conflicting tie at the latest order is deliberately unresolved. */
    {
        const char *mode[] = {"mode"};
        memoria_state_fact conflict[] = {
            {"a", "device alpha", "mode", "active", 9, 0.95},
            {"b", "device alpha", "mode", "idle", 9, 0.99},
        };
        r = memoria_composed_state_resolve(
            "device alpha", mode, 1,
            conflict, sizeof(conflict) / sizeof(conflict[0]));
        CHECK(r.hit == 0);
        CHECK(r.ambiguous == 1);
    }

    /* Equal latest values are not a semantic conflict; strongest source wins. */
    {
        const char *mode[] = {"mode"};
        memoria_state_fact corroborated[] = {
            {"weak", "device alpha", "mode", "active", 10, 0.60},
            {"strong", "device alpha", "mode", "ACTIVE", 10, 0.93},
        };
        r = memoria_composed_state_resolve(
            "device alpha", mode, 1,
            corroborated, sizeof(corroborated) / sizeof(corroborated[0]));
        CHECK(r.hit == 1);
        CHECK(eq(r.items[0].memory_id, "strong"));
        CHECK(r.confidence > 0.929 && r.confidence < 0.931);
    }

    /* Duplicate requested properties are invalid rather than duplicated output. */
    {
        const char *duplicate[] = {"mode", "MODE"};
        r = memoria_composed_state_resolve(
            "device alpha", duplicate, 2,
            facts, sizeof(facts) / sizeof(facts[0]));
        CHECK(r.hit == 0);
    }

    return 0;
}
