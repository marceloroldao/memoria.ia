# v0.96 Natural-Language Noise Findings

This note records the first controlled move from synthetic semantic probes to noisier held-out natural-language formulations.

## Token-router result

The existing token-oriented semantic router was evaluated by selecting one representative learned token from each held-out sentence. On the 20-query controlled corpus, this approach achieved only about 60% total accuracy.

Representative errors included:

- a sentence describing total loss of internet access being pulled toward `router_failure` through the token `acesso`;
- account-block language being confused with router-failure context;
- cable/fiber language occasionally being attracted to equipment-failure context;
- high-latency language being confused with optical-loss context.

This is a negative result. The failure is primarily representational: a single token does not preserve enough of the sentence-level evidence.

## Sentence-profile experiment

`SentenceSemanticRouterV96` was introduced as a separate non-neural experiment. It builds sparse content-word profiles for each concept from example sentences and scores the full held-out query sentence using inverse concept frequency weighting.

Equivalent local execution on the same small corpus improved total accuracy from about 60% to about 80% while retaining 0 false positives at the conservative tested threshold (`threshold=0.14`, `min_margin=0.02`). Remaining failures were mostly conservative abstentions plus a difficult boundary between outage and high-latency language.

## Interpretation

The result does **not** establish general natural-language understanding. It shows that whole-sentence sparse evidence is materially more robust than choosing a single representative token in this corpus.

The token router is therefore retained for trajectory/lexical experiments, while sentence-level routing is evaluated separately for natural-language entry points. No neural encoder is used in either case.

Next validation requirements:

1. larger held-out corpus;
2. paraphrase variation;
3. domain transfer;
4. explicit confusion matrix;
5. threshold calibration without using the test set;
6. sentence-level candidate pruning/scaling;
7. comparison with a simple conventional lexical baseline.

The published v0.95.1 baseline remains unchanged.
