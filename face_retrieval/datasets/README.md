# Datasets

Place each **public benchmark** dataset (downloaded from its official source,
under its own licence) in the matching folder below. The pipeline auto-detects
whichever are present — none are bundled, and nothing is downloaded for you.

> Use only datasets you are authorised to use. This project is for research and
> benchmarking of missing-person retrieval; it does not scrape images or touch
> live feeds.

```
datasets/
  lfw/           <Person_Name>/<Person_Name>_0001.jpg ...        (face retrieval)
  vggface2/      test/<id>/*.jpg   (or train/<id>/*.jpg)         (face retrieval)
  widerface/     WIDER_val/images/...  + wider_face_split/*.txt  (face DETECTION)
  crowdhuman/    Images/*.jpg + annotation_val.odgt              (person DETECTION)
  market1501/    bounding_box_train|test/, query/                (person ReID, optional)
  msmt17/        train/, test/, list_*.txt                       (person ReID, optional)
```

Expected layouts (what the loaders parse):

| Dataset | Identity / label source | Used for |
|---|---|---|
| **LFW** | sub-folder name | face retrieval / verification |
| **VGGFace2** | `<split>/<id>/` folder | face retrieval / verification |
| **WIDER FACE** | `wider_face_*_bbx_gt.txt` boxes | detector evaluation |
| **CrowdHuman** | `.odgt` full-body / head boxes | detector evaluation |
| **Market-1501** | `0002_c1s1_...jpg` → id `0002`, cam `1` | person ReID (optional) |
| **MSMT17** | filename id + camera | person ReID (optional) |

Quick smoke test without any of these: point the CLI at any folder of
identity-labelled images with `--source sample --path <folder>` (sub-folders =
identities, or flat files like `alice_0.jpg`, `alice_1.jpg`, `bob_0.jpg`).

Check what's detected:

```
python -m face_retrieval.cli datasets
```
