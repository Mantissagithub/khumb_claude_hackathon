"""Satellite-ready data-assimilation seam.

Setu is meant to be a *living* system: during the mela, an external density
observation (satellite / drone / CCTV-zone occupancy) arrives periodically, and
the simulation nudges its state toward what was actually observed so its forecasts
track reality. This module defines the observation artifact and the assimilation
hook (the injection point). The real satellite source is out of scope here — only
the seam is built, and it is exercised with a synthetic observation.
"""

from .observation import Observation, assimilate, simulated_density

__all__ = ["Observation", "assimilate", "simulated_density"]
