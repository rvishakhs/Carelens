"""Audit exposes no ports of its own -- it is a terminal for other modules' events
plus an explicit-call sink (see service.py `AuditService.log`). Nothing outside this
module should ever need to depend on an audit interface."""
