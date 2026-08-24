# Memoria.ia — Native Windows Product Alpha

This installation path runs Memoria.ia directly on Windows without Docker, WSL, Hyper-V, or a Linux virtual machine.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer (64-bit recommended)
- Internet access for the first dependency installation

Docker and hardware virtualization are not required.

## Install

Open Command Prompt in the repository root and run:

```cmd
install-windows.bat
```

The installer:

1. verifies Python >= 3.10;
2. creates `.venv` in the repository;
3. installs the `[product]` dependencies;
4. creates `.env` from `.env.example` if `.env` does not exist;
5. creates a local `data` directory.

It never overwrites an existing `.env`.

## Configure

Edit `.env`. At minimum set a unique organization ID and a strong `MEMORIA_API_KEY`.

The Docker-oriented example contains:

```env
MEMORIA_DATA_DIR=/data
```

The Windows launcher automatically translates exactly `/data` to the repository's local `data` directory. You may instead set an absolute Windows path, for example:

```env
MEMORIA_DATA_DIR=C:\Users\your-user\MemoriaData
```

For the first local test use:

```env
MEMORIA_LLM_PROVIDER=mock
```

No OpenAI or Gemini key is required for the mock-provider test.

## Start

```cmd
start-memoria.bat
```

Default local URL:

```text
http://127.0.0.1:8080
```

Health endpoint:

```text
http://127.0.0.1:8080/api/v1/health
```

The launcher binds to `127.0.0.1` by default so the alpha is not exposed to the LAN unintentionally. Set `MEMORIA_HOST=0.0.0.0` only when remote access is intentionally required and the network/security implications are understood.

## Stop

Press `Ctrl+C` in the server window.

## Persistence

State is persisted under `MEMORIA_DATA_DIR`. Closing or restarting Memoria.ia does not delete that directory.

## Updating

The native Windows path intentionally uses a repository-local virtual environment. When switching versions, rerun:

```cmd
install-windows.bat
```

This updates product dependencies while preserving `.env` and the configured data directory.

## Security status

This is a Product Alpha and remains `not-security-reviewed`. The native launcher defaults to localhost and should be used for local/private evaluation until the production security gate is completed.
