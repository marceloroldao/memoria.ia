# BDR extraction status — Memoria.ia v1.0 candidate

This branch intentionally extracts the validated BDR persistence path without merging the historical `experiment/bdr-primary-linux` lineage wholesale.

## Present on this branch

- BDR v1.1 Python adapter boundary;
- Linux/SQLite backend selection policy;
- explicit fallback and fail-closed behavior;
- focused selector tests.

## Still required before promotion

- direct `AtomicDatabase` native binding;
- build plumbing pinned to Resolutive-DB v1.1.0;
- BDR/SQLite behavioral-equivalence tests;
- per-memory atomic-sequence validation;
- deferred-durability validation;
- torn-final-write recovery test;
- reopen/durable-sequence preservation;
- complete Product Alpha regression in both SQLite and Linux-BDR configurations.

No semantic-router, trajectory-policy or unrelated research experiment is permitted into this PR merely because it existed on the historical BDR branch.
