#include "semantic_consolidation_kernel.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

static const char *nz(const char *s) { return s ? s : ""; }

static int normalized_equal(const char *a, const char *b) {
    size_t ia = 0, ib = 0;
    int pending_space_a = 0, pending_space_b = 0;
    const unsigned char *ua = (const unsigned char *)nz(a);
    const unsigned char *ub = (const unsigned char *)nz(b);
    for (;;) {
        unsigned char ca, cb;
        while (ua[ia] && isspace(ua[ia])) { pending_space_a = ia != 0; ++ia; }
        while (ub[ib] && isspace(ub[ib])) { pending_space_b = ib != 0; ++ib; }
        if (pending_space_a != pending_space_b && ua[ia] && ub[ib]) return 0;
        pending_space_a = pending_space_b = 0;
        ca = ua[ia]; cb = ub[ib];
        if (!ca || !cb) {
            while (ua[ia] && isspace(ua[ia])) ++ia;
            while (ub[ib] && isspace(ub[ib])) ++ib;
            return ua[ia] == 0 && ub[ib] == 0;
        }
        if (ca < 128 && cb < 128) {
            if (tolower(ca) != tolower(cb)) return 0;
            ++ia; ++ib;
            continue;
        }
        /* UTF-8 is compared byte-exact in this low-level kernel. Higher layers
         * may canonicalize accents before constructing supports. */
        if (ca != cb) return 0;
        ++ia; ++ib;
    }
}

static int same_claim(const memoria_semantic_support *a, const memoria_semantic_support *b) {
    return normalized_equal(a->namespace_id, b->namespace_id) &&
           normalized_equal(a->subject, b->subject) &&
           normalized_equal(a->predicate, b->predicate) &&
           normalized_equal(a->object, b->object);
}

static int root_seen(const memoria_semantic_candidate *c, const char *root) {
    size_t i;
    for (i = 0; i < c->support_count; ++i)
        if (strcmp(c->factual_root_ids[i], nz(root)) == 0) return 1;
    return 0;
}

static int valid_support(const memoria_semantic_support *s) {
    return s && s->factual_active && s->subject && *s->subject &&
           s->predicate && *s->predicate && s->object && *s->object &&
           s->support_memory_id && *s->support_memory_id &&
           s->factual_root_id && *s->factual_root_id;
}

static void copy_text(char *dst, size_t cap, const char *src) {
    if (!dst || !cap) return;
    snprintf(dst, cap, "%s", nz(src));
}

size_t memoria_semantic_consolidation_candidates(
    const memoria_semantic_support *supports,
    size_t support_count,
    size_t min_independent_roots,
    memoria_semantic_candidate *out,
    size_t out_capacity
) {
    size_t i, j, count = 0;
    unsigned char consumed[1024] = {0};
    if (!supports || !out || !out_capacity || min_independent_roots < 2 || support_count > sizeof(consumed)) return 0;

    for (i = 0; i < support_count && count < out_capacity; ++i) {
        memoria_semantic_candidate candidate;
        if (consumed[i] || !valid_support(&supports[i])) continue;
        memset(&candidate, 0, sizeof(candidate));
        copy_text(candidate.namespace_id, sizeof(candidate.namespace_id), supports[i].namespace_id);
        copy_text(candidate.subject, sizeof(candidate.subject), supports[i].subject);
        copy_text(candidate.predicate, sizeof(candidate.predicate), supports[i].predicate);
        copy_text(candidate.object, sizeof(candidate.object), supports[i].object);
        candidate.confidence = 1.0;

        for (j = i; j < support_count; ++j) {
            const memoria_semantic_support *s = &supports[j];
            if (!valid_support(s) || !same_claim(&supports[i], s)) continue;
            consumed[j] = 1;
            if (root_seen(&candidate, s->factual_root_id)) continue;
            if (candidate.support_count >= MEMORIA_SEMANTIC_CONSOLIDATION_MAX_SUPPORTS) continue;
            copy_text(candidate.support_memory_ids[candidate.support_count], MEMORIA_SEMANTIC_CONSOLIDATION_ID_CAP, s->support_memory_id);
            copy_text(candidate.factual_root_ids[candidate.support_count], MEMORIA_SEMANTIC_CONSOLIDATION_ID_CAP, s->factual_root_id);
            if (s->confidence < candidate.confidence) candidate.confidence = s->confidence;
            ++candidate.support_count;
        }
        if (candidate.support_count >= min_independent_roots) out[count++] = candidate;
    }
    return count;
}
