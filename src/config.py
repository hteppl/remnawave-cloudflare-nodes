import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

_API_TOKEN_RE = re.compile(r"^[0-9a-f]{64}$")


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key, "").strip().lower()
    if not value:
        return default
    return value in ("true", "1", "yes")


class Config:
    def __init__(self, config_path: str = "config.yml"):
        load_dotenv()

        self.config_path = Path(config_path)
        self._raw_config: Dict[str, Any] = {}
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            self._raw_config = yaml.safe_load(f)

        return self._substitute_env_vars(self._raw_config)

    def _save(self) -> None:
        with open(self.config_path, "w") as f:
            yaml.dump(self._raw_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        self._config = self._substitute_env_vars(self._raw_config)

    def _substitute_env_vars(self, config: Any) -> Any:
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            pattern = re.compile(r"\$\{([^}]+)}")
            matches = pattern.findall(config)
            result = config
            for var_name in matches:
                var_value = os.getenv(var_name, "")
                result = result.replace(f"${{{var_name}}}", var_value)
            return result
        else:
            return config

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    # --- Environment variables ---

    @property
    def remnawave_url(self) -> str:
        return os.getenv("REMNAWAVE_API_URL", "")

    @property
    def remnawave_api_key(self) -> str:
        return os.getenv("REMNAWAVE_API_KEY", "")

    @property
    def cloudflare_token(self) -> str:
        return os.getenv("CLOUDFLARE_API_TOKEN", "")

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def api_enabled(self) -> bool:
        return _env_bool("API_ENABLED")

    @property
    def api_host(self) -> str:
        return os.getenv("API_HOST", "0.0.0.0")

    @property
    def api_port(self) -> int:
        try:
            return int(os.getenv("API_PORT", "8741"))
        except ValueError:
            return 8741

    @property
    def api_docs_enabled(self) -> bool:
        return _env_bool("API_DOCS")

    @property
    def api_token(self) -> str:
        return os.getenv("API_TOKEN", "")

    @property
    def telegram_enabled(self) -> bool:
        return _env_bool("TELEGRAM_ENABLED")

    @property
    def telegram_bot_token(self) -> str:
        return os.getenv("TELEGRAM_BOT_TOKEN", "")

    @property
    def telegram_chat_id(self) -> str:
        return os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def telegram_topic_id(self) -> int | None:
        topic_id = os.getenv("TELEGRAM_TOPIC_ID", "")
        if topic_id and topic_id.strip():
            try:
                return int(topic_id.strip())
            except ValueError:
                return None
        return None

    @property
    def timezone(self) -> str:
        return os.getenv("TIMEZONE", "UTC")

    @property
    def time_format(self) -> str:
        return os.getenv("TIME_FORMAT", "%d.%m.%Y %H:%M:%S")

    @property
    def language(self) -> str:
        return os.getenv("LANGUAGE", "en")

    @property
    def telegram_notify_dns_changes(self) -> bool:
        return _env_bool("TELEGRAM_NOTIFY_DNS_CHANGES", default=True)

    @property
    def telegram_notify_node_changes(self) -> bool:
        return _env_bool("TELEGRAM_NOTIFY_NODE_CHANGES", default=True)

    @property
    def telegram_notify_errors(self) -> bool:
        return _env_bool("TELEGRAM_NOTIFY_ERRORS", default=True)

    @property
    def telegram_notify_critical(self) -> bool:
        return _env_bool("TELEGRAM_NOTIFY_CRITICAL", default=True)

    @property
    def telegram_notify_api_changes(self) -> bool:
        return _env_bool("TELEGRAM_NOTIFY_API_CHANGES", default=True)

    @property
    def disable_unreachable_hosts(self) -> bool:
        return _env_bool("DISABLE_UNREACHABLE_HOSTS")

    @property
    def telegram_notify_host_changes(self) -> bool:
        return _env_bool("TELEGRAM_NOTIFY_HOST_CHANGES", default=True)

    # --- YAML config ---

    @property
    def check_interval(self) -> int:
        return self.get("remnawave.check-interval", 30)

    @property
    def domains(self) -> list:
        return self.get("domains") or []

    def reload(self) -> None:
        self._config = self._load_config()

    # --- Config mutation methods ---

    def update_check_interval(self, interval: int) -> None:
        self._raw_config.setdefault("remnawave", {})["check-interval"] = interval
        self._save()

    def add_domain(self, domain: str, zones: list) -> None:
        domains = self._raw_config.setdefault("domains", [])
        for d in domains:
            if d.get("domain") == domain:
                raise ValueError(f"Domain '{domain}' already exists")
        domains.append({"domain": domain, "zones": zones})
        self._save()

    def remove_domain(self, domain: str) -> None:
        domains = self._raw_config.get("domains") or []
        new_domains = [d for d in domains if d.get("domain") != domain]
        if len(new_domains) == len(domains):
            raise ValueError(f"Domain '{domain}' not found")
        self._raw_config["domains"] = new_domains
        self._save()

    def add_zone(self, domain: str, zone: dict) -> None:
        for d in self._raw_config.get("domains") or []:
            if d.get("domain") == domain:
                zones = d.setdefault("zones", [])
                for z in zones:
                    if z.get("name") == zone["name"]:
                        raise ValueError(f"Zone '{zone['name']}' already exists for '{domain}'")
                zones.append(zone)
                self._save()
                return
        raise ValueError(f"Domain '{domain}' not found")

    def remove_zone(self, domain: str, zone_name: str) -> None:
        for d in self._raw_config.get("domains") or []:
            if d.get("domain") == domain:
                zones = d.get("zones") or []
                new_zones = [z for z in zones if z.get("name") != zone_name]
                if len(new_zones) == len(zones):
                    raise ValueError(f"Zone '{zone_name}' not found for '{domain}'")
                d["zones"] = new_zones
                self._save()
                return
        raise ValueError(f"Domain '{domain}' not found")

    def update_zone(self, domain: str, zone_name: str, **kwargs) -> None:
        for d in self._raw_config.get("domains") or []:
            if d.get("domain") == domain:
                for z in d.get("zones") or []:
                    if z.get("name") == zone_name:
                        for key, value in kwargs.items():
                            z[key] = value
                        self._save()
                        return
                raise ValueError(f"Zone '{zone_name}' not found for '{domain}'")
        raise ValueError(f"Domain '{domain}' not found")

    def validate(self) -> None:
        missing = []
        if not self.remnawave_url:
            missing.append("REMNAWAVE_API_URL")
        if not self.remnawave_api_key:
            missing.append("REMNAWAVE_API_KEY")
        if not self.cloudflare_token:
            missing.append("CLOUDFLARE_API_TOKEN")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        if self.api_enabled:
            token = self.api_token
            if not token:
                raise ValueError(
                    "API_TOKEN is required when API_ENABLED is true. "
                    "Generate one with: openssl rand -hex 32"
                )
            if not _API_TOKEN_RE.match(token):
                raise ValueError(
                    "API_TOKEN must be a 64-character lowercase hex string. "
                    "Generate one with: openssl rand -hex 32"
                )

    @staticmethod
    def _parse_zone_nodes(zone: dict) -> list:
        """Normalize a zone's node entries from either 'nodes' or legacy 'ips' format.

        Each returned entry has:
          ip      – the IP to write into Cloudflare DNS
          address – the node.address to match in Remnawave (defaults to ip)
        """
        result = []

        for entry in zone.get("nodes") or []:
            if not isinstance(entry, dict):
                continue
            ip = entry.get("ip")
            if not ip:
                continue
            result.append({
                "ip": ip,
                "address": entry.get("address") or ip,
            })

        for ip in zone.get("ips") or []:
            result.append({
                "ip": ip,
                "address": ip,
            })

        return result

    def get_all_zones(self) -> list:
        zones = []
        for domain_config in self.domains:
            domain = domain_config.get("domain")
            for zone in domain_config.get("zones") or []:
                nodes = self._parse_zone_nodes(zone)
                zone_data = {
                    "domain": domain,
                    "name": zone.get("name"),
                    "ttl": zone.get("ttl", 120),
                    "proxied": zone.get("proxied", False),
                    "nodes": nodes,
                    "ips": [n["ip"] for n in nodes],  # backward-compat: list of DNS IPs
                }
                zones.append(zone_data)
        return zones
