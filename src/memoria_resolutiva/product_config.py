from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None


class ProductConfigurationStore:
    """Customer-controlled local product configuration.

    Non-secret configuration and provider credentials are stored separately.
    Provider credentials are never returned by public status methods. The alpha
    local secret file is chmod 0600 and is explicitly not a production secret
    vault; deployments may override all values with environment/container secrets.
    """

    FORMAT = "memoria.ia-product-config-v1"

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.config_path = self.root / "product-config.json"
        self.secrets_path = self.root / "product-secrets.json"
        self.root.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        data = json.loads(path.read_text("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"invalid configuration file: {path.name}")
        return data

    def _atomic_write(self, path: Path, data: dict[str, Any], *, secret: bool = False) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if secret else 0o640)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
            os.chmod(path, 0o600 if secret else 0o640)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def configure_llm(self, *, provider: str, model: str, api_key: str | None = None) -> None:
        provider = provider.strip().lower()
        if provider not in {"openai", "gemini", "mock"}:
            raise ValueError("provider must be one of: openai, gemini, mock")
        model = model.strip()
        if provider != "mock" and not model:
            raise ValueError("model is required for external providers")

        config = self._read_json(self.config_path)
        config["format"] = self.FORMAT
        config["llm"] = {"provider": provider, "model": model or "mock"}
        self._atomic_write(self.config_path, config)

        if api_key is not None:
            api_key = api_key.strip()
            if provider != "mock" and not api_key:
                raise ValueError("api_key cannot be blank when supplied")
            secrets_data = self._read_json(self.secrets_path)
            if provider == "openai":
                secrets_data["OPENAI_API_KEY"] = api_key
            elif provider == "gemini":
                secrets_data["GEMINI_API_KEY"] = api_key
            self._atomic_write(self.secrets_path, secrets_data, secret=True)

    def llm(self) -> LLMRuntimeConfig:
        config = self._read_json(self.config_path)
        llm = config.get("llm") if isinstance(config.get("llm"), dict) else {}
        provider = llm.get("provider")
        model = llm.get("model")
        secrets_data = self._read_json(self.secrets_path)
        api_key = None
        if provider == "openai":
            api_key = secrets_data.get("OPENAI_API_KEY")
        elif provider == "gemini":
            api_key = secrets_data.get("GEMINI_API_KEY")
        return LLMRuntimeConfig(provider=provider, model=model, api_key=api_key)

    def llm_public_status(self) -> dict[str, Any]:
        llm = self.llm()
        return {
            "provider": llm.provider,
            "model": llm.model,
            "credential_configured": bool(llm.api_key) if llm.provider in {"openai", "gemini"} else None,
            "secret_storage": "local-file-0600-alpha" if self.secrets_path.exists() else "not_configured",
        }

    def configure_license(
        self,
        *,
        license_id: str,
        plan: str,
        valid_until: str | None,
        max_nodes: int,
        capabilities: list[str],
    ) -> None:
        if not license_id.strip():
            raise ValueError("license_id is required")
        if max_nodes < 1:
            raise ValueError("max_nodes must be >= 1")
        config = self._read_json(self.config_path)
        config["format"] = self.FORMAT
        config["license"] = {
            "license_id": license_id.strip(),
            "plan": plan.strip() or "early_access",
            "valid_until": valid_until or None,
            "max_nodes": max_nodes,
            "capabilities": sorted({c.strip() for c in capabilities if c and c.strip()}),
        }
        self._atomic_write(self.config_path, config)

    def license_public_status(self) -> dict[str, Any] | None:
        config = self._read_json(self.config_path)
        license_data = config.get("license")
        if not isinstance(license_data, dict):
            return None
        return dict(license_data)
