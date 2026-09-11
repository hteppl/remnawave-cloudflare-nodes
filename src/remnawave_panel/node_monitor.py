from typing import List

from remnawave.models import NodeResponseDto

from .client import RemnawaveClient
from ..utils.logger import get_logger


class NodeStatus:
    """A Remnawave node plus derived health; unknown attributes proxy to the underlying DTO."""

    def __init__(self, node: NodeResponseDto):
        self.node = node
        self.is_healthy: bool = node.is_connected and not node.is_disabled

    def __getattr__(self, name: str):
        return getattr(self.node, name)

    @property
    def unhealthy_reasons(self) -> List[str]:
        reasons = []
        if not self.node.is_connected:
            reasons.append("disconnected")
        if self.node.is_disabled:
            reasons.append("disabled")
        if not (self.node.versions and self.node.versions.xray):
            reasons.append("no xray")
        return reasons

    def __repr__(self):
        status = "healthy" if self.is_healthy else "unhealthy"
        return f"NodeStatus(name={self.node.name}, address={self.node.address}, status={status})"


class NodeMonitor:
    def __init__(self, client: RemnawaveClient):
        self.client = client
        self.logger = get_logger(__name__)

    async def check_nodes(self) -> List[NodeStatus]:
        statuses = [NodeStatus(node) for node in await self.client.get_nodes()]
        for status in statuses:
            self.logger.debug(repr(status))

        healthy = sum(s.is_healthy for s in statuses)
        self.logger.info(f"Fetched {len(statuses)} nodes: {healthy} online, {len(statuses) - healthy} unhealthy")
        return statuses
