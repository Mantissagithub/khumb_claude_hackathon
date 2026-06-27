"""Social Force Model constants (Helbing, Farkas & Vicsek, Nature 2000).

These are the canonical values that reproduce realistic crush dynamics, the
"faster-is-slower" effect, and clogging at bottlenecks. Grouped in a dataclass so
a scenario can perturb them (e.g. panic raises desired speed) without globals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SFMParams:
    A: float = 2000.0       # social repulsion strength (N)
    B: float = 0.08         # social repulsion range (m)
    k: float = 1.2e5        # body-force (compression) stiffness (kg/s^2)
    kappa: float = 2.4e5    # sliding-friction coefficient (kg/(m·s))
    tau: float = 0.5        # acceleration relaxation time (s)
    r_cut: float = 2.0      # neighbour interaction cutoff (m)
    v_max_factor: float = 1.3   # speed clamp as a multiple of desired speed
    panic_speed_boost: float = 1.0  # panic=1 multiplies desired speed by (1+this)
