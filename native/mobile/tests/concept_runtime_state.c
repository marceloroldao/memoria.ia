#define _XOPEN_SOURCE 700
#include "concept_identity_bdr.h"
#include "concept_identity_kernel.h"
#include "concept_identity_state.h"
#include "concept_runtime_state.h"
#include "memoria_mobile.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>

static memoria_concept_definition defn(
    const char *id, const char *ns, const char *canonical,
    const char *const *aliases, size_t alias_count
) {
    memoria_concept_definition d;
    memset(&d, 0, sizeof(d));
    d.concept_id = id;
    d.namespace_name = ns;
    d.canonical_name = canonical;
    d.aliases = aliases;
    d.alias_count = alias_count;
    return d;
}

int main(void) {
    char path[] = "/tmp/memoria-concept-runtime-XXXXXX";
    memoria_concept_index seed;
    memoria_concept_state_row rows[MEMORIA_CONCEPT_MAX_CONCEPTS];
    memoria_concept_bdr *store = NULL;
    memoria_concept_runtime *runtime = NULL;
    memoria_mobile_handle *mobile = NULL;
    const memoria_concept_index *index;
    memoria_concept_resolution r;
    size_t row_count = 0;
    const char *aliases[] = {"ddp", "diferença de potencial"};
    memoria_concept_definition voltage = defn(
        "concept:voltage", "electronics", "voltage", aliases, 2
    );
    assert(mkdtemp(path) != NULL);
    memoria_concept_index_init(&seed);
    assert(memoria_concept_register(&seed, &voltage) == MEMORIA_CONCEPT_OK);
    assert(memoria_concept_state_export(&seed, rows, MEMORIA_CONCEPT_MAX_CONCEPTS, &row_count) == MEMORIA_CONCEPT_OK);
    assert(row_count == 1);
    assert(memoria_concept_bdr_open(path, "org-runtime", &store));
    assert(memoria_concept_bdr_save(store, rows, row_count));
    assert(memoria_concept_bdr_sync(store));
    memoria_concept_bdr_close(store);
    
    assert(memoria_concept_runtime_open(path, "org-runtime", &runtime));
    index = memoria_concept_runtime_index(runtime);
    assert(index != NULL);
    r = memoria_concept_resolve(index, "electronics", "DDP");
    assert(r.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(r.concept_id, "concept:voltage") == 0);
    memoria_concept_runtime_close(runtime);
    runtime = NULL;
    
    /* The public Native lifecycle must also load the same persisted concept state. */
    assert(memoria_mobile_open(path, "org-runtime", &mobile) == MEMORIA_MOBILE_OK);
    assert(memoria_mobile_flush(mobile) == MEMORIA_MOBILE_OK);
    memoria_mobile_close(mobile);
    mobile = NULL;
    
    assert(memoria_concept_runtime_open(path, "org-runtime", &runtime));
    index = memoria_concept_runtime_index(runtime);
    r = memoria_concept_resolve(index, "electronics", "diferença de potencial");
    assert(r.status == MEMORIA_CONCEPT_HIT);
    assert(strcmp(r.concept_id, "concept:voltage") == 0);
    memoria_concept_runtime_close(runtime);
    return 0;
}
