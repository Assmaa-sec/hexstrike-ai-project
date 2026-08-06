"""
Job model + store. A pipeline run is a long, staged, streamable thing, so it is
modeled as a Job with a status, an event log, and a result. Today the store is
in-process (the CLI runs one job); the eventual web layer swaps in a real backend
and streams the same events to the browser. Nothing else in the pipeline needs to
change for that.
"""

from __future__ import annotations
