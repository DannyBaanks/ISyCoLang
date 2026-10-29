"""Estados de terminación no exitosos (spec §9)."""
from __future__ import annotations


class IsyError(Exception):
    status = "ERROR"

    def __init__(self, code: str, at: str | None = None, detail: str = ""):
        super().__init__(f"{self.status}({code}) at {at}: {detail}")
        self.code = code
        self.at = at
        self.detail = detail


class InvalidProgram(IsyError):
    status = "INVALID_PROGRAM"


class RuntimeFault(IsyError):
    status = "ERROR"


class LimitReached(IsyError):
    status = "LIMIT_REACHED"


class HostTimeout(IsyError):
    status = "TIMEOUT"
