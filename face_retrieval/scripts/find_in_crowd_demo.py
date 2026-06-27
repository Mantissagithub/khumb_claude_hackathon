"""Demo: find a clean missing-person photo among faces in CROWD frames.

Gallery  = several scene frames, each with MANY faces (e.g. a 17-person photo).
Query    = one clean single-face photo of the person we're looking for.
Output   = which frame + which face (bbox) + camera/time, and an annotated image.

Run from repo root:  python -m face_retrieval.scripts.find_in_crowd_demo
"""
import os
import warnings

warnings.filterwarnings("ignore")

from face_retrieval.config import get_logger, load_config, set_seed
from face_retrieval.modules import visualization as viz
from face_retrieval.modules.dataset_loader import Sample
from face_retrieval.pipeline import SearchPipeline

F = "backend/_testdata/faces"
C = "backend/_testdata/crowd"


def main():
    cfg = load_config()
    set_seed(int(cfg.project.seed))
    log = get_logger("kumbh", "INFO")
    pipe = SearchPipeline(cfg, log)

    # crowd "camera frames": a 17-face group photo + others as distractor frames
    scenes = [Sample(os.path.join(F, p)) for p in
              ("personB_1.jpg", "personC_0.jpg", "personA_3.jpg", "personC_1.jpg")]
    scenes += [Sample(os.path.join(C, p)) for p in ("saree_0.jpg", "saree_1.jpg")]
    pipe.build_crowd_gallery(scenes)

    queries = [("Obama", os.path.join(F, "personB_0.jpg")),
               ("Modi", os.path.join(F, "personA_0.jpg"))]
    for name, qpath in queries:
        res = pipe.find_in_crowd(qpath, top_k=5)
        print(f"\n=== query: {name}  ({os.path.basename(qpath)}) ===")
        if not res:
            print("  no face in query"); continue
        verdict = ("CONFIDENT MATCH" if res["confident_match"]
                   else f"NO CONFIDENT MATCH (best < {res['threshold']}) -> needs human review")
        print(f"  verdict: {verdict}")
        for m in res["matches"]:
            print(f"  #{m['rank']} score={m['score']:.3f}  frame={os.path.basename(m['scene_path']):<14}"
                  f" bbox={[int(v) for v in m['bbox']]}  cam={m['camera_id']} @"
                  f"({m['lat']:.5f},{m['lng']:.5f}) {m['timestamp']}")
        top = res["matches"][0]
        others = [mm["bbox"] for mm in pipe.crowd_meta
                  if mm["scene_path"] == top["scene_path"]]
        out = os.path.join(cfg.paths.output_dir, f"crowd_found_{name}.png")
        viz.highlight_in_scene(top["scene_path"], top["bbox"], out, others,
                               label=f"{name} {top['score']:.2f}")
        print(f"  annotated frame -> {out}  ({len(others)} faces in that frame)")


if __name__ == "__main__":
    main()
