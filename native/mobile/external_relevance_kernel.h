#ifndef MEMORIA_EXTERNAL_RELEVANCE_KERNEL_H
#define MEMORIA_EXTERNAL_RELEVANCE_KERNEL_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct memoria_external_relevance_policy {
    double min_query_coverage;
    size_t min_anchor_matches;
    size_t early_window_tokens;
} memoria_external_relevance_policy;

typedef struct memoria_external_relevance_result {
    size_t query_content_tokens;
    size_t matched_query_tokens;
    size_t content_tokens;
    size_t early_matched_query_tokens;
    double query_coverage;
    double early_match_ratio;
    double relevance_score;
    int accepted;
} memoria_external_relevance_result;

int memoria_external_relevance_evaluate(
    const char *query,
    const char *content,
    const memoria_external_relevance_policy *policy,
    memoria_external_relevance_result *out
);

#ifdef __cplusplus
}
#endif
#endif
