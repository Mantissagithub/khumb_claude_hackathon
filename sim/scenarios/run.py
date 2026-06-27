"""Scenario specs + the runner that drives the sim and emits the situation report."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from shared.schema import SituationReport
from sim.controllables import Deployment
from sim.engine import SimConfig, Simulation
from sim.geometry import RAMKUND, Corridor, build_navfield
from sim.io import build_situation_report, corridor_cameras, write_density_csv
from sim.metrics import MetricsRecorder

ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "artifacts"


def _const(rate: float) -> Callable[[float], float]:
    return lambda t: rate


def _snan(t: float) -> float:
    """Free-flow, then a 4x Amrit-Snan surge that ramps up, holds, and relaxes."""
    if t < 20:
        return 2.0
    if t < 40:
        return 2.0 + (8.0 - 2.0) * (t - 20) / 20.0  # ramp up over 20 s
    if t < 110:
        return 8.0                                   # sustained surge
    if t < 130:
        return 8.0 - (8.0 - 2.0) * (t - 110) / 20.0  # relax
    return 2.0


@dataclass
class ScenarioSpec:
    name: str
    arrival: Callable[[float], float]
    duration: float
    panic_at: Optional[float] = None     # stampede: time to trigger panic
    evacuate: bool = False               # flip goal to the top exit
    evac_at: float = 0.0
    notes: str = ""


SCENARIOS: dict[str, ScenarioSpec] = {
    "baseline":   ScenarioSpec("baseline", _const(2.0), duration=150.0,
                               notes="Steady free-flow arrivals; the do-nothing reference."),
    "snan_surge": ScenarioSpec("snan_surge", _snan, duration=160.0,
                               notes="Amrit Snan 4x density spike over the ghat throat."),
    "stampede":   ScenarioSpec("stampede", _snan, duration=160.0, panic_at=70.0,
                               notes="Surge plus a panic trigger at t=70s -> faster-is-slower crush."),
    "evacuation": ScenarioSpec("evacuation", _const(6.0), duration=180.0, evacuate=True, evac_at=70.0,
                               notes="Corridor fills, then goal flips ghat->exit at t=70s; measure egress."),
}


def run_scenario(
    name: str,
    deployment: Optional[Deployment] = None,
    seed: int = 0,
    cell_m: float = 1.0,
    record_every: int = 10,
    write_dir: Optional[Path] = None,
    quiet: bool = True,
) -> tuple[Simulation, MetricsRecorder, SituationReport]:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario {name!r}; choose from {list(SCENARIOS)}")
    spec = SCENARIOS[name]

    cor = Corridor(RAMKUND)
    nav = build_navfield(cor)
    sim = Simulation(cor, nav, arrival_rate=spec.arrival, cfg=SimConfig(dt=0.02, seed=seed),
                     controllables=deployment)
    rec = MetricsRecorder(sim, cell_m=cell_m)

    n_steps = int(round(spec.duration / sim.cfg.dt))
    for s in range(n_steps):
        t = sim.t
        if spec.panic_at is not None and t >= spec.panic_at and sim.n:
            sim.panic[:] = 1.0  # sustained panic raises desired speed (crush)
        if spec.evacuate and t >= spec.evac_at and not sim.cfg.sink_at_top:
            sim.nav = build_navfield(cor, exit_top=True)  # goal flips to the exit
            sim.cfg.sink_at_top = True
            sim.arrival_rate = _const(0.0)                # no new arrivals during evac
            if sim.n:
                sim.panic[:] = 0.4
        sim.step()
        if s % record_every == 0:
            rec.record(sim)

    cameras = corridor_cameras(cor)
    if deployment is not None:
        cameras = deployment.apply_cctv(cameras)
    report = build_situation_report(spec.name, cor, rec, cameras, spec.duration, notes=spec.notes)

    if write_dir is not None:
        write_dir = Path(write_dir)
        write_dir.mkdir(parents=True, exist_ok=True)
        (write_dir / f"{name}_situation.json").write_text(report.to_json())
        write_density_csv(rec, write_dir / f"{name}_density.csv")
        if not quiet:
            print(f"  wrote {write_dir / (name + '_situation.json')}")
    return sim, rec, report


def _summary(name: str, sim: Simulation, rec: MetricsRecorder) -> None:
    print(f"[{name}] peak_pressure={rec.global_peak_pressure:.2f}  "
          f"separations={len(sim.separations)}  throughput={sim.arrived_count}  "
          f"egress={rec.egress_time_s():.0f}s")
    for s in rec.subzone_density():
        print(f"    {s.name:14s} mean={s.mean_density:.2f} peak={s.peak_density:.2f} p/m^2")


def main(argv: list[str]) -> None:
    name = argv[0] if argv else "snan_surge"
    sim, rec, report = run_scenario(name, write_dir=ARTIFACTS / name, quiet=False)
    _summary(name, sim, rec)
    print(f"  pressure points: {len(report.pressure_points)}  "
          f"separation hotspots: {len(report.separation_hotspots)}  "
          f"cctv: {len(report.cctv_inventory)}  units: {len(report.available_units)}")


if __name__ == "__main__":
    main(sys.argv[1:])
