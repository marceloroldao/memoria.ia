#include "../memory_space.h"

#include <assert.h>

int main(void) {
    assert(memoria_memory_space_for_source_type("user_assertion") == MEMORIA_MEMORY_SPACE_FACTUAL);
    assert(memoria_memory_space_for_source_type("user_correction") == MEMORIA_MEMORY_SPACE_FACTUAL);
    assert(memoria_memory_space_for_source_type("external_import") == MEMORIA_MEMORY_SPACE_FACTUAL);
    assert(memoria_memory_space_for_source_type("derived_relation") == MEMORIA_MEMORY_SPACE_FACTUAL);
    assert(memoria_memory_space_for_source_type("assistant_generated") == MEMORIA_MEMORY_SPACE_GENERATIVE);
    assert(memoria_memory_space_for_source_type("retrieved_replay") == MEMORIA_MEMORY_SPACE_GENERATIVE);
    assert(memoria_may_be_factual_root("assistant_generated") == 0);
    assert(memoria_may_be_factual_root("retrieved_replay") == 0);
    assert(memoria_may_be_factual_root("user_assertion") == 1);
    return 0;
}
