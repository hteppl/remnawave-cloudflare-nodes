from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class NodeIn(BaseModel):
    ip: str                         # IP to write into Cloudflare DNS
    address: Optional[str] = None  # node.address to match in Remnawave (e.g. Tailscale IP); defaults to ip


class ZoneIn(BaseModel):
    name: str
    ttl: int = Field(default=120, ge=1)
    proxied: bool = False
    ips: Optional[List[str]] = None
    nodes: Optional[List[NodeIn]] = None

    @model_validator(mode="after")
    def validate_has_entries(self) -> "ZoneIn":
        if not self.ips and not self.nodes:
            raise ValueError("At least one of 'ips' or 'nodes' must be provided")
        return self

    @property
    def dns_ips(self) -> List[str]:
        return [n.ip for n in self.nodes or []] + list(self.ips or [])


class ZonePatch(BaseModel):
    ttl: Optional[int] = Field(default=None, ge=1)
    proxied: Optional[bool] = None
    ips: Optional[List[str]] = Field(default=None, min_length=1)
    nodes: Optional[List[NodeIn]] = None


class DomainIn(BaseModel):
    domain: str
    zones: List[ZoneIn] = Field(min_length=1)


class ConfigPatch(BaseModel):
    check_interval: Optional[int] = Field(default=None, ge=5)
