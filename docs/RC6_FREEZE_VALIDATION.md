# Memoria.ia v1.0.0-rc6 — cumulative freeze validation

Status: freeze candidate validation

Candidate baseline commit before release-metadata changes:

`bcef1111f17be06d8f4c26e78bce4a55cf8e1fbd`

No new runtime features are permitted on this freeze branch. Only regression fixes, documentation, packaging and release-metadata alignment may follow if required by validation.

## Functional scope accumulated since RC5

- bounded structural relational activation up to two hops;
- separate navigation budget and LLM-context budget;
- native/Python activation parity and edge deduplication;
- query-aware relational context ranking;
- composed entity→attribute chains before the LLM;
- open-vocabulary predicate ranking;
- graph-backed implicit predicate cues;
- session→profile semantic-cue fallback with user/application isolation;
- graph-declared semantic roles for predicates and concepts;
- bounded semantic activation planner with maximum two concepts;
- semantic activation resolver integrated with ProductChatService;
- automatic server wiring for semantic chat activation;
- factual-projection contamination barrier excluding assistant_generated evidence;
- preserved Android/mobile ABI compatibility and native runtime validation.

## Required cumulative gates

The candidate is not ready to freeze until all release-blocking checks are green on this exact branch head:

1. v0.96 semantic validation;
2. product-alpha validation, including container restart and backup/restore acceptance;
3. product application credentials;
4. Android mobile ABI;
5. layered performance baseline;
6. Automatic Context when triggered by the changed paths.

## Cumulative behavioral checkpoints

The regression suite must preserve all of the following:

- direct resolution precedence before relational expansion;
- session direct lookup before profile direct lookup;
- no more than two activation concepts;
- no more than two structural hops in the validated chat path;
- no semantic expansion from undeclared arbitrary predicates;
- semantic_role metadata remains internal and is not sent as factual context to the LLM;
- open-vocabulary predicates remain valid without fixed attribute whitelists;
- graph-backed semantic cues remain namespace/user isolated;
- relations too large for the prompt budget may still act as structural navigation bridges;
- generated assistant content cannot become authoritative factual projection evidence;
- alternatives may remain in context, but query-relevant relational chains are ranked first.

## Freeze decision

If all required gates are green with no unresolved release-blocking regression, this branch may be declared the functional freeze for `v1.0.0-rc6`.

After that declaration, do not add automatic semantic-role learning or other new runtime behavior to RC6. Such work belongs to the post-RC6 development line.
