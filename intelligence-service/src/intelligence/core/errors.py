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