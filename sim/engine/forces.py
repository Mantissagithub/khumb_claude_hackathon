"""Numba-accelerated Social Force Model kernel.

Per agent i the force is (Helbing-Farkas-Vicsek 2000):

    f_i = m_i (v0_i e_i − v_i)/τ                              # driving toward ghat
        + Σ_j [ A·exp((r_ij−d_ij)/B) + k·g(r_ij−d_ij) ] n_ij  # social + body
            + κ·g(r_ij−d_ij)·Δv_ji^t · t_ij                   # sliding friction
        + wall term (same form, against the nearest wall)

where g(x)=max(x,0), n_ij is the unit vector from j to i, t_ij its tangent.

Neighbour search uses a uniform spatial-hash grid (cell = interaction cutoff), so
each agent only checks its 3×3 cell neighbourhood — O(N) not O(N²). The grid is
built with numpy each step; the inner force loop is JIT-compiled with numba.
"""

from __future__ import annotations

import numpy as np
from numba import njit


def build_cell_list(px, py, x_min, y_min, cs, gx, gy):
    """Bucket agents into a uniform grid. Returns (order, cell_start, cell_count)."""
    cx = np.clip(((px - x_min) / cs).astype(np.int64), 0, gx - 1)
    cy = np.clip(((py - y_min) / cs).astype(np.int64), 0, gy - 1)
    cell = cy * gx + cx
    order = np.argsort(cell, kind="stable")
    counts = np.bincount(cell, minlength=gx * gy)
    start = np.zeros(gx * gy + 1, dtype=np.int64)
    start[1:] = np.cumsum(counts)
    return order, start, cx, cy


@njit(cache=True, fastmath=True)
def compute_forces(
    px, py, vx, vy, radius, mass, v0_eff, e_x, e_y,
    wall_dist, wall_nx, wall_ny,
    order, start, cx, cy, gx, gy,
    A, B, k, kappa, tau,
):
    n = px.shape[0]
    fx = np.zeros(n)
    fy = np.zeros(n)
    near = np.zeros(n, dtype=np.int64)   # neighbours within 1 m (local-crush proxy)
    velvar = np.zeros(n)                  # local velocity variance (crowd turbulence)

    for i in range(n):
        # Local kinematics within a 1 m disc, self included, for crowd pressure.
        cnt = 1.0
        svx = vx[i]
        svy = vy[i]
        svx2 = vx[i] * vx[i]
        svy2 = vy[i] * vy[i]
        # --- driving force toward the ghat ------------------------------ #
        fxi = mass[i] * (v0_eff[i] * e_x[i] - vx[i]) / tau
        fyi = mass[i] * (v0_eff[i] * e_y[i] - vy[i]) / tau

        cxi = cx[i]
        cyi = cy[i]
        ri = radius[i]

        # --- agent-agent forces over the 3x3 neighbour cells ------------ #
        for ncy in range(cyi - 1, cyi + 2):
            if ncy < 0 or ncy >= gy:
                continue
            for ncx in range(cxi - 1, cxi + 2):
                if ncx < 0 or ncx >= gx:
                    continue
                cell = ncy * gx + ncx
                for s in range(start[cell], start[cell + 1]):
                    j = order[s]
                    if j == i:
                        continue
                    dx = px[i] - px[j]
                    dy = py[i] - py[j]
                    d = np.sqrt(dx * dx + dy * dy)
                    if d > 2.0 or d < 1e-9:  # r_cut; coincident guard
                        continue
                    if d < 1.0:
                        near[i] += 1
                        cnt += 1.0
                        svx += vx[j]
                        svy += vy[j]
                        svx2 += vx[j] * vx[j]
                        svy2 += vy[j] * vy[j]
                    nx = dx / d
                    ny = dy / d
                    rij = ri + radius[j]
                    overlap = rij - d
                    # social repulsion (always) + body compression (contact only)
                    frep = A * np.exp(overlap / B)
                    if overlap > 0.0:
                        frep += k * overlap
                    fxi += frep * nx
                    fyi += frep * ny
                    # sliding friction (contact only), tangential
                    if overlap > 0.0:
                        tx = -ny
                        ty = nx
                        dvt = (vx[j] - vx[i]) * tx + (vy[j] - vy[i]) * ty
                        ff = kappa * overlap * dvt
                        fxi += ff * tx
                        fyi += ff * ty

        # --- wall force (nearest wall, precomputed normal) -------------- #
        dw = wall_dist[i]
        if dw < 2.0:
            overlap_w = ri - dw
            fwall = A * np.exp(overlap_w / B)
            if overlap_w > 0.0:
                fwall += k * overlap_w
            fxi += fwall * wall_nx[i]
            fyi += fwall * wall_ny[i]
            if overlap_w > 0.0:  # wall friction opposes tangential motion
                tx = -wall_ny[i]
                ty = wall_nx[i]
                dvt = -(vx[i] * tx + vy[i] * ty)
                ff = kappa * overlap_w * dvt
                fxi += ff * tx
                fyi += ff * ty

        fx[i] = fxi
        fy[i] = fyi
        # Velocity variance = sum of per-component variances within the 1 m disc.
        mvx = svx / cnt
        mvy = svy / cnt
        velvar[i] = (svx2 / cnt - mvx * mvx) + (svy2 / cnt - mvy * mvy)
        if velvar[i] < 0.0:  # guard tiny negatives from round-off
            velvar[i] = 0.0

    return fx, fy, near, velvar
