"""Rein — fairness-first drone corridor planning.

Rein plans Amazon Prime Air delivery corridors so that no household bears a
disproportionate share of the noise, and lets the affected community shape
those corridors conversationally.

The package is organised by the engines described in the specification:

    geo          — parcels, projections, town definitions
    acoustics    — rotor source model, propagation, annoyance  (Phase 2)
    fairness     — cost field, routing, leximin, respite       (Phase 3)
    mcp          — the Model Context Protocol server           (Phase 4)
    verification — Phase 1 evidence-producing analyses
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.1.0"
