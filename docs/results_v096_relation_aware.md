# v0.96 relation-aware event/state experiment

Status: experimental; not a production default.

## Motivation

The frozen adversarial development set showed that bag-of-words similarity could not reliably distinguish entity identity from event/state. The first state-aware vector expansion reduced open-set false positives but diluted similarity and collapsed known recall.

This experiment keeps lexical similarity unchanged and applies event/state consistency as a separate gate. It also learns positive negation polarity from the existing training examples, rather than assuming every negated token contradicts a concept.

## GitHub Actions results

Python 3.12 / Ubuntu runner. Full suite remained green:

- full suite: 299 passed;
- trajectory contrastive unit tests: 3 passed;
- workflow conclusion: success.

On the same 64-query frozen adversarial development set:

### Original trajectory-contrastive baseline

- accuracy: 0.640625;
- known recall: 0.666667;
- open-set false-positive rate: 0.4375;
- wrong-known-class rate: 0.041667;
- known abstention rate: 0.291667.

### Relation-aware, first scope implementation

- accuracy: 0.6875;
- known recall: 0.708333;
- open-set false-positive rate: 0.375;
- wrong-known-class rate: 0.041667;
- known abstention rate: 0.25.

### Relation-aware with bounded scope + learned positive negation polarity

- accuracy: 0.71875;
- known recall: 0.75;
- open-set false-positive rate: 0.375;
- wrong-known-class rate: 0.0625;
- known abstention rate: 0.1875.

The scope/polarity correction recovered valid cases that the naive negation gate rejected. It also demonstrated that `sem X` can be positive evidence for some concepts (for example an outage learned with absence of connectivity), so negation cannot be treated as a universal contradiction.

## Current failure mode

The dominant remaining open-set errors are entity-only or entity-heavy matches: a query mentioning a router, fiber, account, network or optical power can be routed to a failure concept even when the query describes a neutral/maintenance state. This indicates that the next problem is evidence sufficiency for **event/state**, not lexical entity recognition.

## Scientific note

The 64-query adversarial set has now been inspected repeatedly and should be treated as a development set for subsequent architecture changes. Any later claim of generalization must use a newly constructed untouched holdout set.
