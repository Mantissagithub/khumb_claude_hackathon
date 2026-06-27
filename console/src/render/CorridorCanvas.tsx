/** The corridor instrument — renders the live crowd, density heat field,
 * separation alarm rings, and suggested deployment posts onto a canvas. Reads
 * the latest GPU/CPU frame from a ref so the 60 fps draw loop never re-renders
 * React. Visual language matches standalone.html (the design spec).
 */

import { useEffect, useRef } from "react";
import type { Corridor } from "../sim/corridor";
import { TYPE_COLORS } from "../sim/params";
import type { FrameData } from "../sim/engine";
import type { DeployPlan } from "../plan/deploy";
import type { Ring } from "../sim/useWebGPUSim";

interface Props {
  corridor: Corridor;
  frameRef: React.MutableRefObject<FrameData | null>;
  ringsRef: React.MutableRefObject<Ring[]>;
  plan: DeployPlan;
  deployed: Array<{ lng: number; lat: number; radiusM: number }>;
  panicOn: boolean;
  onPanicAt: (x: number, y: number) => void;
  onPeak?: (p: number) => void; // optional: report live peak density
}

/** Pre-render a cute chibi creature sprite per type (large head, eyes, belly,
 * tiny feet). Kept upright — no rotation needed, chibi looks odd rotated. */
function makePersonSprite(color: string): HTMLCanvasElement {
  const S = 28;
  const c = document.createElement("canvas");
  c.width = S; c.height = S;
  const g = c.getContext("2d")!;
  g.translate(S / 2, S / 2);

  // derive a slightly darker shade for outlines
  // parse hex color into r,g,b and darken by 40%
  const hex = color.replace("#", "");
  const r0 = parseInt(hex.slice(0, 2), 16);
  const g0 = parseInt(hex.slice(2, 4), 16);
  const b0 = parseInt(hex.slice(4, 6), 16);
  const dark = `rgb(${Math.round(r0 * 0.55)},${Math.round(g0 * 0.55)},${Math.round(b0 * 0.55)})`;

  // tiny feet — two small ellipses at the bottom
  g.fillStyle = dark;
  g.beginPath(); g.ellipse(-3, 9.5, 2.5, 1.6, 0, 0, 6.283); g.fill();
  g.beginPath(); g.ellipse(3, 9.5, 2.5, 1.6, 0, 0, 6.283); g.fill();

  // body / belly — rounded, slightly lighter
  g.fillStyle = color;
  g.strokeStyle = dark;
  g.lineWidth = 0.9;
  g.beginPath(); g.ellipse(0, 5.5, 4.5, 4.5, 0, 0, 6.283); g.fill(); g.stroke();

  // large rounded head — dominant feature (~55% of height)
  g.fillStyle = color;
  g.strokeStyle = dark;
  g.lineWidth = 1.0;
  g.beginPath(); g.arc(0, -3.5, 7.5, 0, 6.283); g.fill(); g.stroke();

  // white eyes
  g.fillStyle = "#ffffff";
  g.beginPath(); g.ellipse(-2.4, -4.2, 2.0, 2.2, 0, 0, 6.283); g.fill();
  g.beginPath(); g.ellipse(2.4, -4.2, 2.0, 2.2, 0, 0, 6.283); g.fill();

  // dark pupils
  g.fillStyle = "#1a1a2e";
  g.beginPath(); g.arc(-2.2, -4.0, 1.0, 0, 6.283); g.fill();
  g.beginPath(); g.arc(2.2, -4.0, 1.0, 0, 6.283); g.fill();

  // pupil glints
  g.fillStyle = "#ffffff";
  g.beginPath(); g.arc(-1.8, -4.4, 0.35, 0, 6.283); g.fill();
  g.beginPath(); g.arc(2.6, -4.4, 0.35, 0, 6.283); g.fill();

  return c;
}

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
function heatRGBA(dens: number): [number, number, number, number] {
  const t = Math.min(dens / 6, 1);
  let r, g, b;
  if (t < 0.5) {
    const u = t / 0.5;
    r = lerp(56, 245, u); g = lerp(189, 166, u); b = lerp(248, 35, u);
  } else {
    const u = (t - 0.5) / 0.5;
    r = lerp(245, 255, u); g = lerp(166, 59, u); b = lerp(35, 48, u);
  }
  return [r, g, b, Math.min(0.12 + t * 0.82, 0.9)];
}

export default function CorridorCanvas({
  corridor, frameRef, ringsRef, plan, deployed, panicOn, onPanicAt, onPeak,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // keep latest props in refs so the rAF loop reads fresh values
  const planRef = useRef(plan);
  const deployedRef = useRef(deployed);
  const panicRef = useRef(panicOn);
  const panicPt = useRef({ x: 0, y: corridor.cfg.throatLenM });
  planRef.current = plan;
  deployedRef.current = deployed;
  panicRef.current = panicOn;

  useEffect(() => {
    const cv = canvasRef.current!;
    const ctx = cv.getContext("2d")!;
    const cor = corridor;
    const heat = document.createElement("canvas");
    heat.width = cor.nx; heat.height = cor.ny;
    const hctx = heat.getContext("2d")!;
    const himg = hctx.createImageData(cor.nx, cor.ny);
    const sprites = TYPE_COLORS.map(makePersonSprite);
    const lostSprite = makePersonSprite("#ff5347");

    let W = 0, H = 0, DPR = 1, raf = 0;
    const resize = () => {
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      const r = cv.getBoundingClientRect();
      W = r.width; H = r.height;
      cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const scale = () => Math.min(W / cor.cfg.wideWidthM, H / cor.cfg.lengthM) * 0.96;
    const sx = (x: number) => W / 2 + x * scale();
    const sy = (y: number) => H * 0.98 - y * scale();
    const halfW = (y: number) => cor.widthAt(y) / 2;

    const path = () => {
      ctx.beginPath();
      ctx.moveTo(sx(-halfW(0)), sy(0));
      for (let y = 0; y <= cor.cfg.lengthM; y += 1.5) ctx.lineTo(sx(-halfW(y)), sy(y));
      for (let y = cor.cfg.lengthM; y >= 0; y -= 1.5) ctx.lineTo(sx(halfW(y)), sy(y));
      ctx.closePath();
    };

    const click = (e: MouseEvent) => {
      const r = cv.getBoundingClientRect();
      const x = (e.clientX - r.left - W / 2) / scale();
      const y = (H * 0.98 - (e.clientY - r.top)) / scale();
      panicPt.current = { x, y };
      onPanicAt(x, y);
    };
    cv.addEventListener("click", click);

    const draw = () => {
      raf = requestAnimationFrame(draw);
      const f = frameRef.current;
      ctx.clearRect(0, 0, W, H);

      // channel fill
      path();
      const g = ctx.createLinearGradient(0, sy(cor.cfg.lengthM), 0, sy(0));
      g.addColorStop(0, "#0d1622"); g.addColorStop(1, "#0a1118");
      ctx.fillStyle = g; ctx.fill();

      // range grid + heat (clipped to channel)
      ctx.save(); path(); ctx.clip();
      ctx.strokeStyle = "rgba(255,255,255,0.035)"; ctx.lineWidth = 1;
      for (let y = 10; y < cor.cfg.lengthM; y += 10) {
        ctx.beginPath(); ctx.moveTo(sx(-cor.cfg.wideWidthM / 2), sy(y)); ctx.lineTo(sx(cor.cfg.wideWidthM / 2), sy(y)); ctx.stroke();
      }
      let peak = 0;
      if (f) {
        const area = cor.cellM * cor.cellM;
        const data = himg.data;
        for (let iy = 0; iy < cor.ny; iy++) {
          for (let ix = 0; ix < cor.nx; ix++) {
            const dens = f.density[iy * cor.nx + ix] / area;
            if (dens > peak) peak = dens;
            const o = ((cor.ny - 1 - iy) * cor.nx + ix) * 4;
            if (dens <= 0.05) { data[o + 3] = 0; continue; }
            const [r, gg, b, a] = heatRGBA(dens);
            data[o] = r; data[o + 1] = gg; data[o + 2] = b; data[o + 3] = a * 255;
          }
        }
        hctx.putImageData(himg, 0, 0);
        ctx.imageSmoothingEnabled = true;
        ctx.filter = "blur(7px)";
        ctx.globalCompositeOperation = "lighter";
        ctx.drawImage(heat, sx(-cor.cfg.wideWidthM / 2), sy(cor.cfg.lengthM), cor.cfg.wideWidthM * scale(), cor.cfg.lengthM * scale());
        ctx.filter = "none"; ctx.globalCompositeOperation = "source-over";
      }
      ctx.restore();

      // throat danger band
      const tw = halfW(cor.cfg.throatLenM) * scale();
      ctx.fillStyle = "rgba(255,59,48,0.05)";
      ctx.fillRect(W / 2 - tw, sy(0), tw * 2, sy(cor.cfg.throatLenM) - sy(0));
      ctx.strokeStyle = "rgba(255,59,48,0.25)"; ctx.setLineDash([4, 5]);
      ctx.beginPath(); ctx.moveTo(W / 2 - tw - 6, sy(cor.cfg.throatLenM)); ctx.lineTo(W / 2 + tw + 6, sy(cor.cfg.throatLenM)); ctx.stroke();
      ctx.setLineDash([]);

      // walls
      path(); ctx.strokeStyle = "rgba(120,160,200,0.35)"; ctx.lineWidth = 1.5; ctx.stroke();

      // ghat sink glow
      const gw = halfW(0) * scale(), gyl = sy(0);
      const rg = ctx.createLinearGradient(0, gyl - 26, 0, gyl + 4);
      rg.addColorStop(0, "rgba(56,189,248,0)"); rg.addColorStop(1, "rgba(125,211,252,0.5)");
      ctx.fillStyle = rg; ctx.fillRect(W / 2 - gw, gyl - 26, gw * 2, 30);
      ctx.strokeStyle = "rgba(165,230,255,0.85)"; ctx.lineWidth = 2.5;
      ctx.shadowColor = "rgba(56,189,248,0.8)"; ctx.shadowBlur = 14;
      ctx.beginPath(); ctx.moveTo(W / 2 - gw, gyl); ctx.lineTo(W / 2 + gw, gyl); ctx.stroke();
      ctx.shadowBlur = 0;

      // agents — person glyphs (LOD to dots when zoomed out / dense)
      if (f) {
        const ph = Math.max(8, 1.6 * scale());
        const useSprite = ph >= 9 && f.count <= 4200;
        if (useSprite) {
          for (let i = 0; i < f.count; i++) {
            if (f.lost[i]) continue;
            const px = f.state[i * 4];
            if (px > 1e4) continue;
            ctx.drawImage(sprites[f.typeId[i]] ?? sprites[0], sx(px) - ph / 2, sy(f.state[i * 4 + 1]) - ph / 2, ph, ph);
          }
          // separated pilgrims — red glyph + glow on top
          ctx.shadowColor = "rgba(255,59,48,0.9)"; ctx.shadowBlur = 9;
          for (let i = 0; i < f.count; i++) {
            if (!f.lost[i]) continue;
            const px = f.state[i * 4]; if (px > 1e4) continue;
            ctx.drawImage(lostSprite, sx(px) - ph / 2, sy(f.state[i * 4 + 1]) - ph / 2, ph, ph);
          }
          ctx.shadowBlur = 0;
        } else {
          const ar = Math.max(1.5, 0.26 * scale());
          ctx.globalCompositeOperation = "lighter";
          for (let i = 0; i < f.count; i++) {
            const px = f.state[i * 4];
            if (px > 1e4 || f.lost[i]) continue;
            ctx.fillStyle = TYPE_COLORS[f.typeId[i]] ?? "#9cc";
            ctx.beginPath(); ctx.arc(sx(px), sy(f.state[i * 4 + 1]), ar, 0, 6.283); ctx.fill();
          }
          ctx.globalCompositeOperation = "source-over";
          for (let i = 0; i < f.count; i++) {
            if (!f.lost[i]) continue;
            const px = f.state[i * 4]; if (px > 1e4) continue;
            ctx.fillStyle = "#ff3b30"; ctx.shadowColor = "rgba(255,59,48,0.9)"; ctx.shadowBlur = 8;
            ctx.beginPath(); ctx.arc(sx(px), sy(f.state[i * 4 + 1]), ar + 0.6, 0, 6.283); ctx.fill();
            ctx.shadowBlur = 0;
          }
        }
      }

      // separation alarm rings (aged here)
      const rings = ringsRef.current;
      for (let k = rings.length - 1; k >= 0; k--) {
        const r = rings[k]; r.age++;
        if (r.age > 150) { rings.splice(k, 1); continue; }
        const a = 1 - r.age / 150;
        ctx.strokeStyle = `rgba(255,59,48,${a * 0.8})`; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(sx(r.x), sy(r.y), 3 + r.age * 0.4, 0, 6.283); ctx.stroke();
      }

      // panic epicentre
      if (panicRef.current) {
        const t = (performance.now() / 600) % 1;
        const p = panicPt.current;
        ctx.strokeStyle = `rgba(255,59,48,${0.7 * (1 - t)})`; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(sx(p.x), sy(p.y), 6 + t * 26, 0, 6.283); ctx.stroke();
        ctx.fillStyle = "#ff3b30"; ctx.beginPath(); ctx.arc(sx(p.x), sy(p.y), 3, 0, 6.283); ctx.fill();
      }

      // faint dashed suggestion rings (always shown so operator sees recommendation pre-deploy)
      ctx.setLineDash([4, 5]);
      for (const post of planRef.current.posts) {
        const [x, y] = cor.proj.toXY(post.lng, post.lat);
        const R = 8 * scale();
        ctx.strokeStyle = "rgba(52,211,153,0.25)"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(sx(x), sy(y), R, 0, 6.283); ctx.stroke();
      }
      ctx.setLineDash([]);

      // deployed officers: coverage ring + officer glyph
      if (deployedRef.current.length > 0) {
        for (const d of deployedRef.current) {
          const [x, y] = cor.proj.toXY(d.lng, d.lat);
          const coverR = d.radiusM * scale();
          // translucent coverage ring
          ctx.fillStyle = "rgba(52,211,153,0.07)";
          ctx.strokeStyle = "rgba(52,211,153,0.4)";
          ctx.lineWidth = 1.2;
          ctx.beginPath(); ctx.arc(sx(x), sy(y), coverR, 0, 6.283); ctx.fill(); ctx.stroke();
          // officer glyph: navy rounded body + green cap arc + white cross + glow
          const cx = sx(x), cy = sy(y);
          const bodyR = Math.max(5, 5.5 * Math.min(scale() / 4, 1));
          ctx.shadowColor = "rgba(52,211,153,0.9)"; ctx.shadowBlur = 10;
          // body — navy rounded rect-like ellipse
          ctx.fillStyle = "#13283a";
          ctx.beginPath(); ctx.arc(cx, cy + 1, bodyR, 0, 6.283); ctx.fill();
          ctx.shadowBlur = 0;
          // cap arc — green semicircle on top
          ctx.fillStyle = "#34d399";
          ctx.beginPath(); ctx.arc(cx, cy - bodyR * 0.3, bodyR * 0.75, Math.PI, 0); ctx.fill();
          // white cross
          ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.moveTo(cx - 2, cy + 1); ctx.lineTo(cx + 2, cy + 1);
          ctx.moveTo(cx, cy - 1); ctx.lineTo(cx, cy + 3);
          ctx.stroke();
        }
        ctx.shadowBlur = 0;
      }

      onPeak?.(peak);
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      cv.removeEventListener("click", click);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [corridor]);

  return <canvas ref={canvasRef} />;
}
