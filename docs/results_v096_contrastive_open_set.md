# v0.96 Contrastive Open-Set Learning

## Motivation

The sentence-level sparse router improved noisy natural-language routing, but hard open-set negatives remained problematic. Scalar gates based only on score, runner-up margin, shared-term fraction, or weighted query coverage overlap substantially with valid short queries and therefore cannot safely reject all semantically adjacent negatives.

Examples of the failure mode include:

- a completed-payment receipt being attracted toward `payment_delay` because both mention payment;
- a contact/profile update being attracted toward `account_block` because both mention user/account/cadastro;
- ONU power-supply maintenance being attracted toward `optical_loss` because both mention ONU.

This is a semantic-boundary problem, not a candidate-count problem.

## Experimental response

`ContrastiveSentenceSemanticRouterV96` adds sparse negative profiles per concept.

A positive concept profile answers:

> what evidence supports concept X?

A counterexample profile answers:

> what evidence is close to X but must not be resolved as X?

At resolution time the inherited positive decision is retained only when:

`positive_score - negative_score >= min_contrast_margin`

No embedding or neural network is used.

## Online-learning interpretation

Counterexamples can be added after a false positive without deleting or rewriting the positive concept profile. This makes open-set correction incremental and auditable:

1. observe normal positive experience;
2. resolve a query;
3. if a semantically adjacent false positive is identified, record it as a counterexample for that concept;
4. future related queries are evaluated against both positive and negative memory.

## Current status

This is experimental. Unit tests cover two targeted corrections:

- completed payment vs `payment_delay`;
- profile/contact update vs `account_block`.

The next benchmark must determine whether contrastive correction generalizes to paraphrases and whether negative profiles reduce known-class recall. It must also test catastrophic over-rejection as counterexamples accumulate.

The baseline v0.95.1 remains unchanged.
