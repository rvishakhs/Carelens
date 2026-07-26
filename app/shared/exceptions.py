"""Error hierarchy shared by all modules -> mapped to consistent API responses in main.py."""


class CareLensError(Exception):
    """Base class for all application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)
        self.message = message or self.code


class NotFoundError(CareLensError):
    status_code = 404
    code = "not_found"


class ValidationError(CareLensError):
    status_code = 422
    code = "validation_error"


class PermissionDeniedError(CareLensError):
    status_code = 403
    code = "permission_denied"


class UnauthenticatedError(CareLensError):
    status_code = 401
    code = "unauthenticated"


class ConflictError(CareLensError):
    status_code = 409
    code = "conflict"


class TenantIsolationError(CareLensError):
    """Raised when an operation would cross a care_home_id boundary. Should never happen
    if RLS is configured correctly -- this is a defence-in-depth signal, not the primary control."""

    status_code = 403
    code = "tenant_isolation_violation"