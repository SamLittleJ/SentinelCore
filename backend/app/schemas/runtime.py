from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.security_event import SecurityEventType
from app.schemas.ingest import check_event_time

# The Falco rules kept (from Falco's default rules), and the alert each one
# becomes. Any other rule is answered alike and dropped.
RULES: dict[str, SecurityEventType] = {
    "Terminal shell in container": SecurityEventType.CONTAINER_SHELL_DETECTED,
    "Read sensitive file untrusted": SecurityEventType.SENSITIVE_FILE_READ,
    "Redirect STDOUT/STDIN to Network Connection in Container": (
        SecurityEventType.CONTAINER_NETWORK_TOOL
    ),
    "Netcat Remote Code Execution in Container": (
        SecurityEventType.CONTAINER_NETWORK_TOOL
    ),
}

# Kubernetes' own name rules: a DNS label for namespaces and containers, a
# DNS subdomain for pods.
DnsLabel = Annotated[
    str, StringConstraints(max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
]
DnsSubdomain = Annotated[
    str,
    StringConstraints(
        max_length=253,
        pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$",
    ),
]


class FalcoFields(BaseModel):
    """The few of an alert's output fields that are kept. The rest differ from
    rule to rule and are dropped, the command line among them: it is the
    attacker's, and may carry a password."""

    model_config = ConfigDict(extra="ignore")

    namespace: DnsLabel | None = Field(default=None, alias="k8s.ns.name")
    pod: DnsSubdomain | None = Field(default=None, alias="k8s.pod.name")
    container: DnsLabel | None = Field(default=None, alias="container.name")
    file: Annotated[str, StringConstraints(max_length=255)] | None = Field(
        default=None, alias="fd.name"
    )


class FalcoAlert(BaseModel):
    """One alert, as falcosidekick's webhook output sends it. The server sets
    the alert's type, severity and message; Falco only states what happened."""

    model_config = ConfigDict(extra="forbid")

    uuid: UUID
    rule: Annotated[str, StringConstraints(max_length=255)]
    priority: Literal[
        "Emergency",
        "Alert",
        "Critical",
        "Error",
        "Warning",
        "Notice",
        "Informational",
        "Debug",
    ]
    time: AwareDatetime
    output: Annotated[str, StringConstraints(max_length=10_000)]
    output_fields: FalcoFields
    source: Annotated[str, StringConstraints(max_length=100)]
    tags: Annotated[
        list[Annotated[str, StringConstraints(max_length=100)]], Field(max_length=50)
    ]
    hostname: Annotated[str, StringConstraints(max_length=253)]

    @field_validator("time")
    @classmethod
    def check_time(cls, value: datetime) -> datetime:
        return check_event_time(value)

    @model_validator(mode="after")
    def check_kept_fields(self) -> Self:
        # A kept rule must name where it happened; others are never read.
        event_type = RULES.get(self.rule)
        if event_type is None:
            return self
        fields = self.output_fields
        if not (fields.namespace and fields.pod and fields.container):
            raise ValueError("the alert names no namespace, pod and container")
        if event_type == SecurityEventType.SENSITIVE_FILE_READ and not fields.file:
            raise ValueError("the alert names no file")
        return self
