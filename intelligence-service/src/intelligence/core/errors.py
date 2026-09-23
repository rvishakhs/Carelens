class AccessDenied(Exception):
    pass


class GatewayRejected(Exception):
    pass


class CapacityExceeded(Exception):
    pass

class IdempotencyConflict(Exception):
    pass

class SubmissionBusy(Exception):
    pass

class InvalidShift(ValueError):
    """The requested shift is not eligible for submission."""
    pass

class ExecutionAuthorisationDenied(Exception):
    """The current service or staff permissions do not allow execution."""


class ExecutionAuthorisationUnavailable(Exception):
    """Current permissions could not be checked due to a temporary failure."""
