"""Structured, PII-free logging + metrics.

Unit-tested contract: resident names, notes text, and other clinical free-text must
never reach a log line. Enforced here via a processor that redacts known-sensitive
keys rather than trusting call sites to remember.
"""

import logging
import sys

import structlog

# Keys that must never appear in a log event, however they got there.
_REDACTED_KEYS = {"name", "full_name", "notes", "note_text", "dob", "nhs_number", "address", "phone"}


def _redact_sensitive_fields(_logger, _method_name, event_dict):
    for key in list(event_dict.keys()):
        if key.lower() in _REDACTED_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_sensitive_fields,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)