from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=False)
class ServiceError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        # Never include provider exception text, user payload, or secrets.
        return self.code


def unavailable(dependency: str) -> ServiceError:
    return ServiceError(503, f"{dependency}_unavailable", f"{dependency.capitalize()} is unavailable. Check its backend configuration and retry.", True)


def malformed(operation: str) -> ServiceError:
    return ServiceError(502, "invalid_provider_response", f"The {operation} provider returned an invalid result. Retry the request.", True)
