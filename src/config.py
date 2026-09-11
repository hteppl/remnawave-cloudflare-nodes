import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

import yaml
from dotenv import load_dotenv

from .utils.dns import build_fqdn

_API_TOKEN_RE = re.compile(r"^[0-9a-f]{64}$")
_ENV_VAR_RE = re.compile(r"\$\{([^}]+)}")

T = TypeVar("T")


class ConfigNotFoundError(ValueError):
    """Raised when a domain or zone referenced by a mutation does not exist."""


class ConfigConflictError(ValueError):
    """Raised when adding a domain or zone that already exists."""


def _parse_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


class _Env(Generic[T]):
    """Descriptor reading an environment variable on every access.

    Empty or unparsable values fall back to the default.
    """

    def __init__(self, key: str, default: T, cast: Callable[[str], T] = str):
        self.key = key
        self.default = default
        self.cast = cast

    def __get__(self, instance: Any, owner: type) -> T:
        raw = os.getenv(self.key, "").strip()
        if not raw:
            return self.default
        try:
            return self.cast(raw)
        except ValueError:
            return self.default


@dataclass(frozen=True)
class ZoneNode:
    ip: str  # IP to write into Cloudflare DNS
    address: str  # node.address to match in Remnawave (defaults to ip)


@dataclass(frozen=True)
class Zone:
    domain: str
    name: str
    ttl: int
    proxied: bool
    nodes: List[ZoneNode]

    @property
    def fqdn(self) -> str:
        return build_fqdn(self.name, self.domain)

    @property
    def ips(self) -> List[str]:
        return [n.ip for n in self.nodes]


def parse_zone_nodes(zone: dict) -> List[ZoneNode]:
    """Normalize a raw zone's node entries from either 'nodes' or legacy 'ips' format."""
    nodes = [
        ZoneNode(ip=entry["ip"], address=entry.get("address") or entry["ip"])
        for entry in zone.get("nodes") or []
        if isinstance(entry, dict) and entry.get("ip")
    ]
    nodes += [ZoneNode(ip=ip, address=ip) for ip in zone.get("ips") or []]
    return nodes


class Config:
    # --- Environment variables ---
    remnawave_url = _Env("REMNAWAVE_API_URL", "")
    remnawave_api_key = _Env("REMNAWAVE_API_KEY", "")
    cloudflare_token = _Env("CLOUDFLARE_API_TOKEN", "")
    log_level = _Env("LOG_LEVEL", "INFO")
    language = _Env("LANGUAGE", "en")

    api_enabled = _Env("API_ENABLED", False, _parse_bool)
    api_host = _Env("API_HOST", "0.0.0.0")
    api_port = _Env("API_PORT", 8741, int)
    api_token = _Env("API_TOKEN", "")

    telegram_enabled = _Env("TELEGRAM_ENABLED", False, _parse_bool)
    telegram_bot_token = _Env("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = _Env("TELEGRAM_CHAT_ID", "")
    telegram_topic_id: _Env[Optional[int]] = _Env("TELEGRAM_TOPIC_ID", None, int)
    telegram_notify_dns_changes = _Env("TELEGRAM_NOTIFY_DNS_CHANGES", True, _parse_bool)
    telegram_notify_node_changes = _Env("TELEGRAM_NOTIFY_NODE_CHANGES", True, _parse_bool)
    telegram_notify_errors = _Env("TELEGRAM_NOTIFY_ERRORS", True, _parse_bool)
    telegram_notify_critical = _Env("TELEGRAM_NOTIFY_CRITICAL", True, _parse_bool)
    telegram_notify_api_changes = _Env("TELEGRAM_NOTIFY_API_CHANGES", True, _parse_bool)
    telegram_notify_host_changes = _Env("TELEGRAM_NOTIFY_HOST_CHANGES", True, _parse_bool)

    disable_unreachable_hosts = _Env("DISABLE_UNREACHABLE_HOSTS", False, _parse_bool)

    def __init__(self, config_path: str = "config.yml"):
        load_dotenv()

        self.config_path = Path(config_path)
        self._raw_config: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}
        self.reload()

    # --- Loading ---

    def reload(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            self._raw_config = yaml.safe_load(f) or {}
        self._config = self._substitute_env_vars(self._raw_config)

    def _save(self) -> None:
        with open(self.config_path, "w") as f:
            yaml.dump(self._raw_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        self._config = self._substitute_env_vars(self._raw_config)

    @classmethod
    def _substitute_env_vars(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: cls._substitute_env_vars(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._substitute_env_vars(item) for item in value]
        if isinstance(value, str):
            return _ENV_VAR_RE.sub(lambda m: os.getenv(m.group(1), ""), value)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        value = self._config
        for k in key.split("."):
            if not isinstance(value, dict) or value.get(k) is None:
                return default
            value = value[k]
        return value

    # --- YAML config ---

    @property
    def check_interval(self) -> int:
        return self.get("remnawave.check-interval", 30)

    @property
    def domains(self) -> list:
        return self.get("domains") or []

    def get_all_zones(self) -> List[Zone]:
        return [
            Zone(
                domain=domain_config.get("domain"),
                name=zone.get("name"),
                ttl=zone.get("ttl", 120),
                proxied=zone.get("proxied", False),
                nodes=parse_zone_nodes(zone),
            )
            for domain_config in self.domains
            for zone in domain_config.get("zones") or []
        ]

    # --- Config mutation methods ---

    def _raw_domains(self) -> list:
        return self._raw_config.get("domains") or []

    def _find_domain(self, domain: str) -> dict:
        for d in self._raw_domains():
            if d.get("domain") == domain:
                return d
        raise ConfigNotFoundError(f"Domain '{domain}' not found")

    def _find_zone(self, domain: str, zone_name: str) -> dict:
        for z in self._find_domain(domain).get("zones") or []:
            if z.get("name") == zone_name:
                return z
        raise ConfigNotFoundError(f"Zone '{zone_name}' not found for '{domain}'")

    def has_domain(self, domain: str) -> bool:
        return any(d.get("domain") == domain for d in self.domains)

    def update_check_interval(self, interval: int) -> None:
        self._raw_config.setdefault("remnawave", {})["check-interval"] = interval
        self._save()

    def add_domain(self, domain: str, zones: list) -> None:
        if any(d.get("domain") == domain for d in self._raw_domains()):
            raise ConfigConflictError(f"Domain '{domain}' already exists")
        self._raw_config["domains"] = [*self._raw_domains(), {"domain": domain, "zones": zones}]
        self._save()

    def remove_domain(self, domain: str) -> None:
        self._raw_domains().remove(self._find_domain(domain))
        self._save()

    def add_zone(self, domain: str, zone: dict) -> None:
        zones = self._find_domain(domain).setdefault("zones", [])
        if any(z.get("name") == zone["name"] for z in zones):
            raise ConfigConflictError(f"Zone '{zone['name']}' already exists for '{domain}'")
        zones.append(zone)
        self._save()

    def remove_zone(self, domain: str, zone_name: str) -> None:
        zone = self._find_zone(domain, zone_name)
        self._find_domain(domain)["zones"].remove(zone)
        self._save()

    def update_zone(self, domain: str, zone_name: str, **kwargs) -> None:
        self._find_zone(domain, zone_name).update(kwargs)
        self._save()

    # --- Validation ---

    def validate(self) -> None:
        required = {
            "REMNAWAVE_API_URL": self.remnawave_url,
            "REMNAWAVE_API_KEY": self.remnawave_api_key,
            "CLOUDFLARE_API_TOKEN": self.cloudflare_token,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        if self.api_enabled:
            hint = "Generate one with: openssl rand -hex 32"
            if not self.api_token:
                raise ValueError(f"API_TOKEN is required when API_ENABLED is true. {hint}")
            if not _API_TOKEN_RE.match(self.api_token):
                raise ValueError(f"API_TOKEN must be a 64-character lowercase hex string. {hint}")
