#include "semantic_kernel.h"
#include <assert.h>
#include <string.h>

int main(void) {
    memoria_semantic_source one[] = {
        {"u1", "primary supply voltage is 24 volts", 1.0, 1, "user_assertion", "u1"},
        {"u2", "meeting moved to friday", 1.0, 2, "user_assertion", "u2"}
    };
    memoria_semantic_result r = memoria_semantic_resolve_sources("what is primary supply voltage", one, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "u1") == 0);
    assert(strcmp(r.ultimate_source_memory_id, "u1") == 0);

    memoria_semantic_source echo[] = {
        {"user", "project atlas code is 4729", 1.0, 1, "user_assertion", "user"},
        {"assistant", "the atlas code is 4729", 0.35, 2, "assistant_generated", "user"},
        {"assistant2", "atlas code 4729", 0.35, 3, "assistant_generated", "user"}
    };
    r = memoria_semantic_resolve_sources("atlas code 4729", echo, 3);
    assert(r.hit == 1 && strcmp(r.memory_id, "user") == 0);
    assert(strcmp(r.source_type, "user_assertion") == 0);
    assert(strcmp(r.ultimate_source_memory_id, "user") == 0);
    assert(r.source_authority == 1.0);

    memoria_semantic_source same_root_only_echoes[] = {
        {"echo1", "atlas code 4729", 0.35, 2, "assistant_generated", "source-root"},
        {"echo2", "atlas code is 4729", 0.35, 3, "assistant_generated", "source-root"}
    };
    r = memoria_semantic_resolve_sources("atlas code 4729", same_root_only_echoes, 2);
    assert(r.hit == 1);
    assert(strcmp(r.ultimate_source_memory_id, "source-root") == 0);

    memoria_semantic_source ambiguous[] = {
        {"a", "north laboratory server is atlas", 1.0, 1, "user_assertion", "a"},
        {"b", "south laboratory server is orion", 1.0, 2, "user_assertion", "b"}
    };
    r = memoria_semantic_resolve_sources("laboratory server", ambiguous, 2);
    assert(r.hit == 0);

    /* A question is conversational trajectory, not factual evidence. This also
       protects stores created by older mobile builds that labelled every user
       turn as user_assertion. */
    memoria_semantic_source question_vs_fact[] = {
        {"fact", "delta node capacity is 64 units", 1.0, 1, "user_assertion", "fact"},
        {"question", "what is the delta node capacity?", 1.0, 2, "user_assertion", "question"}
    };
    r = memoria_semantic_resolve_sources("delta node capacity", question_vs_fact, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "fact") == 0);

    /* A verbose generated contradiction must not beat a shorter direct fact
       merely because it repeats more of the query. */
    memoria_semantic_source generated_conflict[] = {
        {"direct", "orion module threshold is 37 units", 1.0, 1, "user_assertion", "direct"},
        {"q", "what is the orion module threshold?", 1.0, 2, "user_assertion", "q"},
        {"generated", "the current orion module threshold is 93 units", 0.35, 3, "assistant_generated", "q"}
    };
    r = memoria_semantic_resolve_sources("current orion module threshold", generated_conflict, 3);
    assert(r.hit == 1 && strcmp(r.memory_id, "direct") == 0);
    assert(strcmp(r.source_type, "user_assertion") == 0);

    /* If a generated answer is the only retrievable member of a query-rooted
       lineage, do not canonicalize back to the question itself. */
    memoria_semantic_source query_root_only[] = {
        {"qroot", "which port is assigned to the beacon?", 1.0, 1, "user_assertion", "qroot"},
        {"answer", "beacon port is seven", 0.35, 2, "assistant_generated", "qroot"}
    };
    r = memoria_semantic_resolve_sources("beacon port seven", query_root_only, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "answer") == 0);

    r = memoria_semantic_resolve_sources("unknown satellite frequency", one, 2);
    assert(r.hit == 0);
    return 0;
}
