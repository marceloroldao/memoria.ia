#ifndef MEMORIA_CONCEPT_IDENTITY_BDR_H
#define MEMORIA_CONCEPT_IDENTITY_BDR_H

#include "concept_identity_state.h"

#include <stddef.h>

typedef struct memoria_concept_bdr memoria_concept_bdr;

int memoria_concept_bdr_open(
    const char *data_dir,
    const char *organization_id,
    memoria_concept_bdr **out
);

int memoria_concept_bdr_save(
    memoria_concept_bdr *store,
    const memoria_concept_state_row *rows,
    size_t row_count
);

int memoria_concept_bdr_save_catalog(
    memoria_concept_bdr *store,
    const memoria_concept_state_row *rows,
    size_t row_count,
    const char *fingerprint
);

int memoria_concept_bdr_load(
    memoria_concept_bdr *store,
    memoria_concept_state_row *rows,
    size_t row_capacity,
    size_t *row_count
);

int memoria_concept_bdr_load_fingerprint(
    memoria_concept_bdr *store,
    char *fingerprint,
    size_t fingerprint_cap
);

int memoria_concept_bdr_sync(memoria_concept_bdr *store);
void memoria_concept_bdr_close(memoria_concept_bdr *store);

#endif
