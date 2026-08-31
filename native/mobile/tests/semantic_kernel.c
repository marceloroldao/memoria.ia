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

    memoria_semantic_source question_vs_fact[] = {
        {"fact", "delta node capacity is 64 units", 1.0, 1, "user_assertion", "fact"},
        {"question", "what is the delta node capacity?", 1.0, 2, "user_assertion", "question"}
    };
    r = memoria_semantic_resolve_sources("delta node capacity", question_vs_fact, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "fact") == 0);

    memoria_semantic_source generated_conflict[] = {
        {"direct", "orion module threshold is 37 units", 1.0, 1, "user_assertion", "direct"},
        {"q", "what is the orion module threshold?", 1.0, 2, "user_assertion", "q"},
        {"generated", "the current orion module threshold is 93 units", 0.35, 3, "assistant_generated", "q"}
    };
    r = memoria_semantic_resolve_sources("current orion module threshold", generated_conflict, 3);
    assert(r.hit == 1 && strcmp(r.memory_id, "direct") == 0);
    assert(strcmp(r.source_type, "user_assertion") == 0);

    memoria_semantic_source query_root_only[] = {
        {"qroot", "which port is assigned to the beacon?", 1.0, 1, "user_assertion", "qroot"},
        {"answer", "beacon port is seven", 0.35, 2, "assistant_generated", "qroot"}
    };
    r = memoria_semantic_resolve_sources("beacon port seven", query_root_only, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "answer") == 0);

    /* Retrieval v2: conversational framing is not a concept. A generic query
       about China must prefer the country overview over a lexically similar
       subtype such as the airline. */
    memoria_semantic_source china[] = {
        {"country", "República Popular da China, também conhecida como China, é um país da Ásia Oriental com capital em Pequim e grande população.", 0.85, 1, "external_import", "country"},
        {"airline", "Air China é uma empresa aérea estatal da República Popular da China com sede em Pequim e voos internacionais.", 0.85, 2, "external_import", "airline"}
    };
    r = memoria_semantic_resolve_sources("me fale sobre a China", china, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "country") == 0);

    /* Generic Moon questions should prefer a direct entity description over a
       narrower page that merely mentions the same concept repeatedly. */
    memoria_semantic_source moon[] = {
        {"moon", "A Lua é o satélite natural da Terra e orbita o planeta.", 0.85, 1, "external_import", "moon"},
        {"phases", "As fases da Lua descrevem a mudança aparente da porção iluminada da Lua durante a lunação.", 0.85, 2, "external_import", "phases"}
    };
    r = memoria_semantic_resolve_sources("o que é a lua", moon, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "moon") == 0);

    /* UTF-8 Portuguese normalization must keep accented concepts intact. */
    memoria_semantic_source portuguese[] = {
        {"p1", "A população do país vive majoritariamente em cidades e fala várias línguas.", 0.85, 1, "external_import", "p1"},
        {"p2", "O motor possui tensão nominal de vinte e quatro volts.", 1.0, 2, "user_assertion", "p2"}
    };
    r = memoria_semantic_resolve_sources("populacao do pais", portuguese, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "p1") == 0);
    r = memoria_semantic_resolve_sources("línguas do país", portuguese, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "p1") == 0);

    /* Public evidence must beat a generated answer when both match the same
       factual query, even if the generated text is more repetitive. */
    memoria_semantic_source public_vs_generated[] = {
        {"public", "A China é um país da Ásia Oriental e sua capital é Pequim.", 0.85, 1, "external_import", "public"},
        {"generated", "China China China é um país e a capital da China é outra cidade.", 0.35, 2, "assistant_generated", "q"}
    };
    r = memoria_semantic_resolve_sources("capital da china", public_vs_generated, 2);
    assert(r.hit == 1 && strcmp(r.memory_id, "public") == 0);

    r = memoria_semantic_resolve_sources("unknown satellite frequency", one, 2);
    assert(r.hit == 0);
    return 0;
}
