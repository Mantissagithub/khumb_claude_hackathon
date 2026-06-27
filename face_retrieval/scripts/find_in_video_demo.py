"""Demo: find a celebrity (clean photo) inside a VIDEO CLIP.

Gallery = frames sampled from the clip (every face per frame indexed).
Query   = one clean hero/celebrity photo.
Output  = ranked frame+timestamp hits, the timeline of confident appearances,
          and an annotated frame with the located face boxed.

Run from repo root:  python -m face_retrieval.scripts.find_in_video_demo
"""
import os
import warnings

warnings.filterwarnings("ignore")

from face_retrieval.config import get_logger, load_config, set_seed
from face_retrieval.modules import visualization as viz
from face_retrieval.pipeline import SearchPipeline

CLIP = "backend/_testdata/video/obama_clip.webm"
QUERY = "backend/_testdata/faces/personB_0.jpg"   # clean Obama portrait


def main():
    cfg = load_config()
    set_seed(int(cfg.project.seed))
    log = get_logger("kumbh", "INFO")
    pipe = SearchPipeline(cfg, log)

    n_frames = pipe.build_gallery_from_video(CLIP, max_frames=60, every_sec=1.5)
    res = pipe.find_in_crowd(QUERY, top_k=10)
    thr = res["threshold"]

    print(f"\n=== query: clean photo of Obama  vs clip ({n_frames} frames sampled) ===")
    print(f"  verdict: {'FOUND' if res['confident_match'] else 'NOT FOUND'} "
          f"(threshold {thr})")
    print("  top hits (face -> frame@time):")
    for m in res["matches"][:6]:
        flag = "OK " if m["confident"] else "  -"
        print(f"   {flag} score={m['score']:.3f}  {m['timestamp']:<8} "
              f"frame_idx={m['frame_idx']:<5} bbox={[int(v) for v in m['bbox']]}")

    # timeline: distinct timestamps with a confident appearance
    times = sorted({m["time_sec"] for m in res["matches"] if m["confident"]})
    print(f"\n  confident appearances at: {[f'{t:.1f}s' for t in times] or 'none'}")

    if res["confident_match"]:
        top = res["matches"][0]
        others = [mm["bbox"] for mm in pipe.crowd_meta
                  if mm["scene_path"] == top["scene_path"]]
        out = os.path.join(cfg.paths.output_dir, "video_found_obama.png")
        viz.highlight_in_scene(top["scene_path"], top["bbox"], out, others,
                               label=f"Obama {top['score']:.2f} @ {top['timestamp']}")
        print(f"\n  annotated frame -> {out}")


if __name__ == "__main__":
    main()
