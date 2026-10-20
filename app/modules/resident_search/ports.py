"""Ports published by the resident-history search module.

The initial deterministic search is HTTP-only. Add a read port here only when
another module genuinely needs to consume saved search results; doing so avoids
turning the search implementation into an accidental cross-module dependency.
"""
