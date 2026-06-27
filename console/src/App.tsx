/** Setu Crowd Command — the operator console. Composes the telemetry rail, the
 * live corridor instrument, and the geo map. Uploading a CSV updates the
 * matching layer; a Chokepoints upload re-anchors the corridor and re-runs.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import "./styles.css";
import { useWebGPUSim } from "./sim/useWebGPUSim";
import CorridorCanvas from "./render/CorridorCanvas";
import GeoMap from "./render/GeoMap";
import { RAMKUND } from "./sim/corridor";
import {
  type DataLayers, type CsvKind, detectKind, loadChokepoints, loadPolice,
  loadZones, loadCameras, loadMissingPrior, pickAnchor, loadDefaults,
} from "./data/csv";

const EMPTY_LAYERS: DataLayers = {
  chokepoints: [], police: [], zones: [], cameras: [], missingPrior: new Map(),
};

const fmt = (n: number) => Math.round(n).toLocaleString("en-IN");

export default function App() {
  const sim = useWebGPUSim();
  const [layers, setLayers] = useState<DataLayers>(EMPTY_LAYERS);
  const [anchor, setAnchor] = useState<[number, number]>([RAMKUND.anchorLat, RAMKUND.anchorLng]);
  const [panicOn, setPanicOn] = useState(false);
  const [surge, setSurgeLocal] = useState(1400);
  const [uploadMsg, setUploadMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const scenarioIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const scenarioStartRef = useRef<number>(0);

  // load bundled defaults on first paint, and feed police into the planner
  useEffect(() => {
    loadDefaults().then((d) => {
      setLayers(d);
      sim.setPolice(d.police);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFile = async (file: File) => {
    const text = await file.text();
    const kind: CsvKind = detectKind(text);
    if (kind === "unknown") {
      setUploadMsg(`Unrecognized CSV — expected chokepoints, police, zones, CCTV, or missing-persons.`);
      return;
    }
    setLayers((prev) => {
      const next = { ...prev };
      if (kind === "chokepoints") {
        next.chokepoints = loadChokepoints(text);
        const a = pickAnchor(next.chokepoints);
        if (a) {
          setAnchor([a.lat, a.lng]);
          sim.reanchor(a.lng, a.lat);
          setUploadMsg(`Chokepoints loaded · corridor re-anchored to ${a.name}`);
        }
      } else if (kind === "police") {
        next.police = loadPolice(text);
        sim.setPolice(next.police);
        setUploadMsg(`${next.police.length} police stations loaded · plan updated`);
      } else if (kind === "zones") {
        next.zones = loadZones(text);
        setUploadMsg(`${next.zones.length} zones loaded`);
      } else if (kind === "cameras") {
        next.cameras = loadCameras(text);
        setUploadMsg(`${next.cameras.length} cameras loaded`);
      } else if (kind === "missing") {
        next.missingPrior = loadMissingPrior(text);
        setUploadMsg(`Missing-person prior updated (${next.missingPrior.size} locations)`);
      }
      return next;
    });
  };

  const onSurge = (v: number) => {
    setSurgeLocal(v);
    sim.setSurge(v);
  };
  const onPanic = () => {
    const next = !panicOn;
    setPanicOn(next);
    sim.setPanic(next);
  };

  const runScenario = (name: "baseline" | "snan" | "stampede") => {
    if (scenarioIntervalRef.current) {
      clearInterval(scenarioIntervalRef.current);
      scenarioIntervalRef.current = null;
    }
    const cor = sim.corridor;
    if (name === "baseline") {
      sim.setPanic(false);
      setPanicOn(false);
      setSurgeLocal(1200);
      sim.setSurge(1200);
      return;
    }
    // snan surge and stampede: ramp 1200→5500 over ~24s wall clock
    scenarioStartRef.current = performance.now();
    if (name === "stampede" && cor) {
      sim.setPanic(false);
      setPanicOn(false);
    }
    scenarioIntervalRef.current = setInterval(() => {
      const elapsed = (performance.now() - scenarioStartRef.current) / 1000; // seconds
      const rampDur = 16; // ramp phase duration
      const t = Math.min(elapsed / rampDur, 1);
      const newSurge = Math.round(1200 + (5500 - 1200) * t);
      setSurgeLocal(newSurge);
      sim.setSurge(newSurge);
      if (name === "stampede" && elapsed >= 12 && cor) {
        sim.setPanic(true);
        sim.setPanicAt(0, cor.cfg.throatLenM);
        setPanicOn(true);
      }
      if (elapsed >= 24) {
        clearInterval(scenarioIntervalRef.current!);
        scenarioIntervalRef.current = null;
      }
    }, 200);
  };

  useEffect(() => {
    return () => {
      if (scenarioIntervalRef.current) clearInterval(scenarioIntervalRef.current);
    };
  }, []);

  const [claudeMsg, setClaudeMsg] = useState("");
  const [claudeFetching, setClaudeFetching] = useState(false);

  const askClaude = async () => {
    setClaudeFetching(true);
    setClaudeMsg("");
    try {
      const resp = await fetch("/api/plan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          hotspots: sim.hotspots,
          police: layers.police.map((p) => ({ name: p.name, lng: p.lng, lat: p.lat })),
          situation: {
            peakDensity: sim.stats.peakDensity,
            separations: sim.stats.separations,
            scenario: "live",
            coveredPct: sim.plan.coveredPct,
          },
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      sim.applyClaudePlan(data);
    } catch (err) {
      setClaudeMsg(`Could not reach planner: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setClaudeFetching(false);
    }
  };

  const { stats, plan, corridor, running, mode, adapterInfo } = sim;
  const risk = useMemo(() => {
    if (stats.peakDensity >= 4) return { cls: "risk-crush", lab: "p/m² · crush risk" };
    if (stats.peakDensity >= 2) return { cls: "risk-dense", lab: "p/m² · dense" };
    return { cls: "risk-safe", lab: "p/m² · safe" };
  }, [stats.peakDensity]);

  const statusCls = mode === "cpu" ? "gpu-cpu" : running ? "" : "paused";
  const statusTxt = mode === "init" ? "Booting" : mode === "cpu" ? "CPU fallback" : running ? "Simulating · GPU" : "Paused";

  return (
    <div className="app">
      {/* ───────── telemetry rail ───────── */}
      <div className="rail">
        <div className="rail-scroll">
          <div>
            <div className="brand"><span className="mark" /><h1>SETU</h1></div>
            <div className="eyebrow" style={{ marginTop: 10 }}>Crowd Command · Simhastha 2027</div>
          </div>

          <div className="loc">
            <div className="name">Ramkund Ghat</div>
            <div className="sub">Panchavati · Nashik — Godavari approach</div>
            <div className={`status ${statusCls}`}><span className="led" /><span>{statusTxt}</span></div>
          </div>

          <div>
            <div className="group-label">Live readout</div>
            <div className="readouts">
              <div className="cell">
                <span className="k">Peak density</span>
                <span className={`v ${risk.cls}`}>{stats.peakDensity.toFixed(1)}</span>
                <span className="u">{risk.lab}</span>
              </div>
              <div className="cell">
                <span className="k">In corridor</span>
                <span className="v" style={{ color: "var(--ink)" }}>{fmt(stats.activeCount)}</span>
                <span className="u">pilgrims</span>
              </div>
              <div className="cell">
                <span className="k">Separations</span>
                <span className="v" style={{ color: "var(--amber)" }}>{fmt(stats.separations)}</span>
                <span className="u">family bonds lost</span>
              </div>
              <div className="cell">
                <span className="k">Hotspots</span>
                <span className="v" style={{ color: "var(--verm)" }}>{fmt(stats.hotspots)}</span>
                <span className="u">separation clusters</span>
              </div>
            </div>
          </div>

          <div className="controls">
            <div className="group-label">Scenario preset</div>
            <div className="btns">
              <button className="btn" onClick={() => runScenario("baseline")}>Baseline</button>
              <button className="btn" onClick={() => runScenario("snan")}>Snan surge</button>
              <button className="btn" onClick={() => runScenario("stampede")}>Stampede</button>
            </div>
            <div className="group-label">Scenario</div>
            <div>
              <div className="slider-head">
                <span className="lab">Arrival surge</span>
                <span className="val">{fmt(surge)}</span>
              </div>
              <input type="range" min={200} max={6000} step={100} value={surge}
                onChange={(e) => onSurge(+e.target.value)} />
              <div className="scale-ticks"><span>Normal</span><span>Snan day</span><span>Amrit Snan 5×</span></div>
            </div>
            <div className="btns">
              <button className="btn" onClick={sim.togglePlay}>{running ? "⏸ Pause" : "▶ Resume"}</button>
              <button className={`btn ${panicOn ? "armed" : ""}`} onClick={onPanic}>
                {panicOn ? "⚡ Panic live" : "⚡ Arm panic"}
              </button>
              <button className="btn wide" onClick={sim.reset}>↺ Reset hotspots</button>
            </div>
            <div className="btns">
              <button className="btn" style={{ color: "var(--green)" }} onClick={sim.deployToPlan}>🛡 Deploy police</button>
              <button className="btn" onClick={sim.clearDeployment}>Stand down</button>
            </div>
            <div className="btns">
              <button className="btn wide" style={{ color: "var(--amber)" }}
                onClick={askClaude} disabled={claudeFetching}>
                {claudeFetching ? "Asking Claude…" : "✦ Ask Claude to plan"}
              </button>
            </div>
            {claudeMsg && <div className="upload-msg">{claudeMsg}</div>}
            <div>
              <div className="group-label">Update geography</div>
              <input ref={fileRef} type="file" accept=".csv" hidden
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }} />
              <div className="upload" role="button" tabIndex={0}
                onClick={() => fileRef.current?.click()}
                onKeyDown={(e) => { if (e.key === "Enter") fileRef.current?.click(); }}>
                <b>Upload a CSV</b> — chokepoints, police, zones, CCTV or missing-persons.<br />
                Coordinates update; chokepoints re-anchor the corridor and re-run.
              </div>
              {uploadMsg && <div className="upload-msg">{uploadMsg}</div>}
            </div>
          </div>

          <div className="plan">
            <div className="plan-head"><span className="dot" />Deployment plan</div>
            {plan.posts.length === 0 ? (
              <div className="plan-idle">
                Run a surge until the throat crushes — Setu maps the separation hotspots,
                then places police posts where they cover the most risk.
              </div>
            ) : (
              <div>
                <div className="coverage">
                  <span className="pct">{plan.coveredPct}%</span>
                  <span className="of">of separation risk covered</span>
                </div>
                <div className="bar">
                  <span className="fill" style={{ width: `${plan.coveredPct}%` }} />
                  <span className="uniform" style={{ left: `${plan.uniformPct}%` }} />
                </div>
                <div className="plan-note">
                  <b>{plan.posts.length} police posts</b> at the throat cover <b>{plan.coveredPct}%</b> of
                  separation risk — vs <b>{plan.uniformPct}%</b> for the same posts spread evenly (marker).
                </div>
                {sim.claudeRationale && (
                  <div className="plan-note" style={{ marginTop: 8, borderLeft: "2px solid var(--amber)", paddingLeft: 8 }}>
                    <b style={{ color: "var(--amber)", fontSize: "0.7rem", letterSpacing: "0.08em" }}>
                      {sim.claudeSource === "claude" ? "CLAUDE" : "HEURISTIC"}
                    </b>
                    {" "}{sim.claudeRationale}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="legend">
            <span className="it"><span className="sw" style={{ background: "#38bdf8" }} />adult</span>
            <span className="it"><span className="sw" style={{ background: "#fbbf24" }} />child</span>
            <span className="it"><span className="sw" style={{ background: "#c084fc" }} />elderly</span>
            <span className="it"><span className="sw" style={{ background: "#fb7185" }} />mobility-impaired</span>
            <span className="it"><span className="sw" style={{ background: "#ff3b30" }} />separated</span>
            <span className="it"><span className="sw" style={{ background: "#34d399" }} />police post</span>
          </div>

          <div className="foot">
            {mode === "cpu"
              ? "WebGPU unavailable — running the CPU fallback at reduced population. "
              : `${adapterInfo}. `}
            Behavioral Social Force Model over real Ramkund geometry — the 2003 approach where 39
            pilgrims died in the throat. Click the field to set the panic epicentre.
          </div>
        </div>
      </div>

      {/* ───────── corridor instrument ───────── */}
      <div className="stage">
        {corridor ? (
          <CorridorCanvas
            corridor={corridor}
            frameRef={sim.frameRef}
            ringsRef={sim.ringsRef}
            plan={plan}
            deployed={sim.deployed}
            panicOn={panicOn}
            onPanicAt={sim.setPanicAt}
          />
        ) : (
          <div className="boot">Initialising crowd model…</div>
        )}
        <div className="hud">
          <div className="corner tl">Approach axis · 60 m</div>
          <div className="corner tr">Throat · 6 m wide</div>
          <div className="corner axis-top">▲ Entrance / Plaza</div>
          <div className="corner axis-bot">Godavari Ghat ▼</div>
          <div className="heat-legend">
            <div className="ramp" />
            <div className="lbls"><span>open</span><span>dense</span><span>crush</span></div>
          </div>
        </div>
        <div className={`alarm ${stats.peakDensity >= 4 ? "on" : ""}`}>
          ⚠ Crush risk — density exceeds 4 p/m² at the throat
        </div>
      </div>

      {/* ───────── geo map ───────── */}
      <div className="map-col">
        <div className="map-head">
          <div className="t">Nashik · Simhastha grounds</div>
          <div className="s">Live separation hotspots + suggested deployment</div>
        </div>
        <div className="leaflet-wrap">
          <GeoMap layers={layers} hotspots={sim.hotspots} plan={plan} center={anchor} deployed={sim.deployed} />
        </div>
        <div className="map-key">
          <span className="it"><span className="sw" style={{ background: "#38bdf8" }} />chokepoint</span>
          <span className="it"><span className="sw" style={{ background: "#a3b6cc" }} />police</span>
          <span className="it"><span className="sw" style={{ background: "#ff3b30" }} />hotspot</span>
          <span className="it"><span className="sw" style={{ background: "#34d399" }} />deploy</span>
        </div>
      </div>
    </div>
  );
}
