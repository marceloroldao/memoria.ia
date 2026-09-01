/*
 * Post-v1 runtime aggregation for explicit composed-state resolution.
 *
 * The validated evidence/episode/promotion runtime remains intact and is
 * included first. The composed-state ABI is then added in the same translation
 * unit so it can read native turn/relation state without exposing or rewriting
 * private v1 structures.
 */
#include "evidence_metrics_runtime.c"
#include "composed_state_mobile.c"
