# SPDX-License-Identifier: Apache-2.0
"""Provider-agnostic deployment types.

An :class:`InferenceSpec` describes *what* to run on an external compute network
(a container image that serves an OpenAI-compatible SIP gateway for one model).
A :class:`Deployment` is the handle a provider returns: an id, a lifecycle
:class:`DeploymentStatus`, and — once provisioned — a reachable ``endpoint``.

Both are deliberately network-neutral: Nosana and Akash adapters translate an
``InferenceSpec`` into their own job/SDL formats and surface their lease/job
state back as a ``Deployment``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ComputeError


class DeploymentStatus(StrEnum):
    """Lifecycle of an external-compute deployment."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    CLOSED = "closed"

    @property
    def is_ready(self) -> bool:
        """True once the workload is serving (still needs an endpoint to use)."""
        return self is DeploymentStatus.RUNNING

    @property
    def is_terminal(self) -> bool:
        """True when no further state change is expected without redeploying."""
        return self in (DeploymentStatus.FAILED, DeploymentStatus.CLOSED)


@dataclass(frozen=True, slots=True)
class InferenceSpec:
    """A request to serve one model as an OpenAI-compatible SIP gateway.

    ``image`` must expose ``port`` and speak the SIP gateway HTTP surface. The
    money-relevant ``input_per_1m``/``output_per_1m`` prices travel with the spec
    so the resulting provider manifest advertises what the node will charge.
    """

    model: str
    image: str
    port: int = 8080
    gpu: bool = True
    gpu_model: str | None = None
    cpu: str = "1"
    memory: str = "8Gi"
    command: list[str] | None = None
    env: dict[str, str] = field(default_factory=dict)
    input_per_1m: float = 0.0
    output_per_1m: float = 0.0
    pricing_unit: str = "usdc"

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ComputeError("InferenceSpec.model must be a non-empty model id")
        if not self.image.strip():
            raise ComputeError("InferenceSpec.image must be a non-empty container image")
        if not (1 <= self.port <= 65_535):
            raise ComputeError(f"InferenceSpec.port out of range: {self.port}")


@dataclass(frozen=True, slots=True)
class Deployment:
    """A handle to a workload provisioned on an external compute network.

    The ``pricing_*`` fields are stamped from the :class:`InferenceSpec` that
    provisioned the node so the advertised provider manifest is structurally
    tied to what the node was deployed to charge (see ``provider_manifest_for``).
    They are ``None`` for handles built outside an adapter's ``deploy``.
    """

    provider: str
    id: str
    model: str
    status: DeploymentStatus
    endpoint: str | None = None
    pricing_unit: str | None = None
    input_per_1m: float | None = None
    output_per_1m: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        """True when the workload is running *and* reachable at an endpoint."""
        return self.status.is_ready and bool(self.endpoint)
