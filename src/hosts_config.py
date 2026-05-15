import os
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml


class HostsConfig:
    """Loads and manages the optional hosts.yml safelist.

    hosts.yml defines which Remnawave host UUIDs the monitor is allowed
    to enable/disable. If the file is absent or empty, the monitor falls
    back to managing ALL hosts whose address matches a managed zone.
    """

    def __init__(self, hosts_path: str = "hosts.yml"):
        self.hosts_path = Path(hosts_path)
        self._uuids: Set[str] = set()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.hosts_path.exists():
            return
        try:
            with open(self.hosts_path, "r") as f:
                data = yaml.safe_load(f)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        entries = data.get("hosts") or []
        if not isinstance(entries, list):
            return
        self._entries = entries
        for entry in entries:
            if isinstance(entry, dict):
                uuid = entry.get("uuid")
                if uuid:
                    self._uuids.add(str(uuid).strip().lower())

    def reload(self) -> None:
        """Reload hosts.yml from disk."""
        self._uuids.clear()
        self._entries = []
        self._load()

    @property
    def uuids(self) -> Set[str]:
        return self._uuids

    @property
    def entries(self) -> List[Dict[str, Any]]:
        return self._entries

    @property
    def enabled(self) -> bool:
        return bool(self._uuids)

    def is_managed(self, uuid: str) -> bool:
        if not self.enabled:
            return True  # No safelist = manage all
        return str(uuid).strip().lower() in self._uuids
