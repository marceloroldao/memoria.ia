# Memoria.ia V2 Server RC1 — deployment checklist

Frozen branch: `freeze/v2-server-rc1`
Frozen commit: `17f95ad6b5408e671acbf408d231563900bef826`
Validated workflow run: `35540382443`

This document is an operational checklist for the first real-server validation of the frozen V2 Server RC1. Do not add feature work to the frozen branch.

## 1. Checkout the exact frozen baseline

```bash
git fetch origin
git checkout freeze/v2-server-rc1
git reset --hard 17f95ad6b5408e671acbf408d231563900bef826
git rev-parse HEAD
```

The last command must print exactly the frozen SHA above.

## 2. Configure the server

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

- `MEMORIA_ORGANIZATION_ID`
- `MEMORIA_ORGANIZATION_NAME`
- `MEMORIA_NODE_ID`
- a long random `MEMORIA_API_KEY`

Keep the validated RC1 runtime settings:

```text
MEMORIA_DATA_DIR=/data
MEMORIA_CONVERSATION_RUNTIME=native
MEMORIA_EPISODIC_RUNTIME=native
MEMORIA_NATIVE_LIB=/usr/local/lib/libmemoria_mobile.so
MEMORIA_LLM_PROVIDER=mock
```

Do not configure an external LLM for the first acceptance pass.

## 3. Build and start

```bash
docker compose build --pull
docker compose up -d
docker compose ps
docker compose logs --tail=100 memoria
```

Health probe:

```bash
curl -fsS http://127.0.0.1:8080/api/v1/health
curl -fsS http://127.0.0.1:8080/api/v1/storage/health
```

The storage health response must report native conversation and episodic runtimes.

## 4. Persistence smoke test

Replace `YOUR_API_KEY` with the configured key.

```bash
curl -fsS \
  -H 'X-Memoria-Key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"role":"user","text":"sensor = active","session_id":"rc1-smoke","order":1}' \
  http://127.0.0.1:8080/api/v1/conversation/ingest

curl -fsS \
  -H 'X-Memoria-Key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"query":"sensor active","session_id":"rc1-smoke"}' \
  http://127.0.0.1:8080/api/v1/conversation/resolve
```

The resolve request must return a HIT containing the persisted context.

## 5. Cold-restart test

```bash
docker compose restart memoria
docker compose ps
```

Wait until healthy, then repeat the resolve request from step 4. It must still return the persisted context.

## 6. Functional memory tests

After the smoke test, exercise the server through the normal conversation interface with isolated sessions.

### A — direct recall

Input:
`Minha camisa é preta.`

Query:
`Qual é a cor da minha camisa?`

Record the exact response, status, confidence and selected context.

### B — temporal change

Inputs in order:
1. `Minha camisa era branca.`
2. `Minha camisa agora é preta.`

Queries:
- `Qual é a cor da minha camisa?`
- `Qual era a cor da minha camisa antes?`
- `O que mudou na minha camisa?`

Do not manually correct an unexpected answer. Preserve the result as evidence.

### C — competing observations / V2 ontogenesis

Inputs in order:
1. `Hoje me acordei feliz.`
2. `Hoje me acordei triste.`
3. `Hoje me acordei feliz.`

Verify that ingestion does not destructively overwrite earlier observations. Capture the resulting recall/inspection evidence before interpreting correctness.

### D — no-LLM boundary

Keep `MEMORIA_LLM_PROVIDER=mock` and verify that native memory resolution works without an external provider call.

## 7. Evidence to preserve

For every failure, record:

- frozen SHA;
- input sequence;
- endpoint/request;
- complete response;
- relevant server log lines;
- whether failure persists after restart;
- whether data was lost or only resolution was wrong.

Do not modify the frozen branch to hide a failing test. Fixes discovered here must be developed separately and promoted only after regression validation.

## Freeze acceptance

RC1 is suitable for server experimentation because the frozen SHA passed the V2 Server Freeze Gate, including Python contracts and the production-container build/start/write/resolve/restart/recover path. It remains an experimental release candidate, not a production-security certification.
