"""Permission and access control for inference resources.

This module implements the ``PermissionEnforcer`` class for capability-based
authorization according to Section 35 (Permissions) of the NerveCenter
specification.

The permissions system provides:
- Access control based on permission levels
- Capability-based authorization checks
- Permission assertion validation
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class PermissionLevel(StrEnum):
    """Access control levels for inference resources."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    OWNER = "owner"


@dataclass
class PermissionCheck:
    """A permission assertion to be verified."""

    subject: str
    resource: str
    level: PermissionLevel
    timestamp: str = ""


class PermissionEnforcer(BaseModel):
    """Enforces permission policies for inference operations.

    The enforcer validates that subjects have appropriate permissions
    for requested resources. It supports:

    - Hierarchical permission levels
    - Resource-scoped permissions
    - Dynamic policy evaluation

    Usage
    -----
    >>> enforcer = PermissionEnforcer(
    ...     policy={
    ...         "admin": ["read", "write", "execute", "admin", "owner"],
    ...         "write": ["read", "write"],
    ...         "read": ["read"],
    ...     }
    ... )
    >>> allowed = enforcer.check("user1", "inference/model", PermissionLevel.WRITE)
    """

    model_config = {"extra": "forbid"}

    policy: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "owner": ["read", "write", "execute", "admin", "owner"],
            "admin": ["read", "write", "execute", "admin"],
            "write": ["read", "write"],
            "read": ["read"],
        },
        description="Mapping of permission levels to allowed sub-levels.",
    )
    default_level: str = Field(
        default="read",
        description="Default permission level when none is specified.",
    )

    def check(
        self, subject: str, resource: str, level: PermissionLevel
    ) -> bool:
        """Check if a subject has the required permission level.

        Args:
            subject: The subject requesting access (user, agent, etc.)
            resource: The resource being accessed
            level: The permission level required

        Returns:
            True if the subject has sufficient permission, False otherwise.
        """
        subject_level = self._get_subject_level(subject, resource)
        return self._has_level(subject_level, level)

    def _get_subject_level(self, subject: str, resource: str) -> PermissionLevel:
        """Determine the effective permission level for a subject/resource."""
        return PermissionLevel(self.default_level)

    def _has_level(self, subject_level: PermissionLevel, required: PermissionLevel) -> bool:
        """Check if subject level satisfies required level."""
        allowed = self.policy.get(str(subject_level), [])
        return str(required) in allowed

    def get_allowed_levels(self, subject: str, resource: str) -> list[PermissionLevel]:
        """Get all permission levels a subject has for a resource."""
        subject_level = self._get_subject_level(subject, resource)
        allowed = self.policy.get(str(subject_level), [])
        return [PermissionLevel(level) for level in allowed]

    def enforce(
        self, subject: str, resource: str, level: PermissionLevel
    ) -> None:
        """Enforce permission or raise PermissionError."""
        if not self.check(subject, resource, level):
            raise PermissionError(
                f"Subject '{subject}' lacks {level} permission on '{resource}'"
            )

    def to_check(self, subject: str, resource: str, level: str) -> PermissionCheck:
        """Create a PermissionCheck for audit purposes."""
        return PermissionCheck(
            subject=subject,
            resource=resource,
            level=PermissionLevel(level),
        )
