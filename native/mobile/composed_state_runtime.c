/*
 * Post-v1 runtime aggregation for explicit composed-state resolution.
 *
 * The validated evidence/episode/promotion runtime remains intact and is
 * included first. The composed-state ABI is then added in the same translation
 * unit so it can read native turn/relation state without exposing or rewriting
 * private v1 structures.
 *
 * Retrieval v2 is intentionally activated only inside this post-v1 composition
 * unit. The frozen v1 semantic resolver remains compiled as the baseline and
 * the adapter itself delegates ranking to it after transient normalization,
 * ambiguity and conceptual-coverage gates.
 */
#include "retrieval_v2_normalization.c"
#include "retrieval_v2_semantic_adapter.c"

#define memoria_semantic_resolve_sources memoria_retrieval_v2_resolve_sources
#include "evidence_metrics_runtime.c"
#undef memoria_semantic_resolve_sources

#include "composed_state_mobile.c"

/* Experimental inference remains additive: it reads the already reconstructed
 * persisted turn/relation graph and never mutates retrieval or stored facts. */
#include "resolutive_inference_mobile.c"
