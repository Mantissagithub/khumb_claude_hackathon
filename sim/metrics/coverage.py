"""CCTV coverage of the high-crowd-pressure zones.

A camera is a cone: position + heading + field-of-view half-angle + range. A
high-pressure grid cell is "covered" if it falls inside some camera's cone.
Coverage = covered high-pressure cells / all high-pressure cells; the uncovered
ones are the blind spots a deployment plan should re-aim a camera toward.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from shared.schema import CameraState
from .recorder import MetricsRecorder


def cctv_coverage(
    rec: MetricsRecorder,
    cameras: list[CameraState],
    pressure_threshold: Optional[float] = None,
) -> dict:
    """Return coverage stats over cells whose peak pressure exceeds a threshold.

    ``pressure_threshold`` defaults to 30% of the observed global peak (floored at
    a small absolute value), i.e. "the cells that actually got dangerous".
    """
    cor = rec.cor
    pp = rec.peak_pressure
    if pressure_threshold is None:
        pressure_threshold = max(0.05, 0.30 * float(pp.max()))

    high = pp >= pressure_threshold
    iy, ix = np.where(high)
    if iy.size == 0:
        return {"coverage": 1.0, "n_high": 0, "n_covered": 0, "blindspots": [], "threshold": pressure_threshold}

    # High-pressure cell centres in local metric coords.
    cx = cor.x_min + (ix + 0.5) * rec.cell_m
    cy = cor.y_min + (iy + 0.5) * rec.cell_m

    covered = np.zeros(iy.size, dtype=bool)
    for cam in cameras:
        camx, camy = cor.proj.to_xy(cam.lng, cam.lat)
        dx = cx - camx
        dy = cy - camy
        dist = np.hypot(dx, dy)
        ang = np.degrees(np.arctan2(dy, dx))               # 0=east, CCW positive
        dang = np.abs((ang - cam.heading_deg + 180) % 360 - 180)
        in_cone = (dist <= cam.range_m) & (dang <= cam.fov_deg / 2.0)
        covered |= in_cone

    n_high = int(iy.size)
    n_covered = int(covered.sum())
    blindspots = []
    for j in np.where(~covered)[0]:
        lng, lat = cor.proj.to_lnglat(float(cx[j]), float(cy[j]))
        blindspots.append({"lng": lng, "lat": lat, "pressure": float(pp[iy[j], ix[j]])})
    blindspots.sort(key=lambda b: b["pressure"], reverse=True)

    return {
        "coverage": n_covered / n_high,
        "n_high": n_high,
        "n_covered": n_covered,
        "blindspots": blindspots,
        "threshold": pressure_threshold,
    }
