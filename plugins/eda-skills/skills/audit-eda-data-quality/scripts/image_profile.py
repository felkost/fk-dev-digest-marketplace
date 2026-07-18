"""Image dataset profiling for computer-vision EDA (audit stage, image data).

Integrity + property distributions + per-channel normalization constants
(fitted on TRAIN only) + dependency-light near-duplicate detection across
splits. Nothing here trains a model.

Pillow and numpy are used directly; OpenCV (cv2) is optional (blur falls back to
a numpy Laplacian). imagehash is NOT required -- a small average hash is
implemented here. See references/computer-vision.md for the full workflow.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import numpy as np


def profile_images(paths: Sequence[str]):
    """Per-image integrity + geometry table (format, mode, size, aspect, corrupt)."""
    import pandas as pd
    from PIL import Image

    rows = []
    for p in paths:
        rec = {"path": str(p), "corrupt": False, "format": None, "mode": None,
               "width": None, "height": None, "channels": None, "aspect": None}
        try:
            with Image.open(p) as im:
                im.verify()  # catches truncated/corrupt files
            with Image.open(p) as im:
                rec.update(format=im.format, mode=im.mode, width=im.width,
                           height=im.height, channels=len(im.getbands()),
                           aspect=round(im.width / im.height, 3) if im.height else None)
        except Exception as e:  # noqa: BLE001
            rec["corrupt"] = True
            rec["error"] = type(e).__name__
        rows.append(rec)
    return pd.DataFrame(rows)


def resolution_summary(profile_df) -> dict:
    """Aggregate the profile table: counts, formats/modes, size and aspect spread."""
    ok = profile_df[~profile_df["corrupt"]]
    return {
        "n_images": int(len(profile_df)),
        "n_corrupt": int(profile_df["corrupt"].sum()),
        "formats": ok["format"].value_counts().to_dict(),
        "modes": ok["mode"].value_counts().to_dict(),
        "width": {k: round(float(v), 1) for k, v in ok["width"].describe().items()} if len(ok) else {},
        "height": {k: round(float(v), 1) for k, v in ok["height"].describe().items()} if len(ok) else {},
        "n_distinct_aspect": int(ok["aspect"].nunique()) if len(ok) else 0,
    }


def channel_stats(images: Iterable, max_images: Optional[int] = None) -> dict:
    """Per-channel mean/std over TRAIN images -> normalization constants.

    ``images``: iterable of ``HxW`` or ``HxWxC`` arrays (or PIL images). Fit on
    the training split only and apply the same constants to val/test. Values are
    scaled to [0,1] when the input looks like 0-255.
    """
    total = total_sq = None
    count = 0
    nimg = 0
    for i, img in enumerate(images):
        if max_images is not None and i >= max_images:
            break
        a = np.asarray(img, dtype=np.float64)
        if a.ndim == 2:
            a = a[..., None]
        if a.size and a.max() > 1.0:
            a = a / 255.0
        c = a.shape[-1]
        flat = a.reshape(-1, c)
        if total is None:
            total = np.zeros(c)
            total_sq = np.zeros(c)
        total += flat.sum(0)
        total_sq += (flat ** 2).sum(0)
        count += flat.shape[0]
        nimg += 1
    if not count:
        return {"mean": [], "std": [], "n_images": 0}
    mean = total / count
    var = np.maximum(total_sq / count - mean ** 2, 0.0)
    return {"mean": [round(float(m), 4) for m in mean],
            "std": [round(float(s), 4) for s in np.sqrt(var)], "n_images": nimg}


def average_hash(img, hash_size: int = 8) -> int:
    """64-bit average perceptual hash (Pillow only, no imagehash)."""
    from PIL import Image

    if not hasattr(img, "convert"):
        img = Image.open(img)
    g = np.asarray(img.convert("L").resize((hash_size, hash_size)), dtype=np.float64)
    bits = (g > g.mean()).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def near_duplicate_pairs(paths: Sequence[str], max_distance: int = 5,
                         hash_size: int = 8) -> list:
    """Candidate near-duplicate ``(path_i, path_j, distance)`` pairs.

    Run this across split boundaries too: near-duplicates in both train and test
    are leakage. Uses a Pillow-only perceptual hash (no extra dependency).
    """
    hashes = [(p, average_hash(p, hash_size)) for p in paths]
    out = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            d = _hamming(hashes[i][1], hashes[j][1])
            if d <= max_distance:
                out.append((hashes[i][0], hashes[j][0], d))
    return out


def blur_score(img) -> float:
    """Variance of the Laplacian (low = blurry). cv2 if available, else numpy."""
    from PIL import Image

    if not hasattr(img, "convert"):
        img = Image.open(img)
    g = np.asarray(img.convert("L"), dtype=np.float64)
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    try:
        import cv2
        return float(cv2.Laplacian(g, cv2.CV_64F).var())
    except Exception:  # cv2 missing OR a partial/stub install lacking Laplacian
        from numpy.lib.stride_tricks import sliding_window_view
        k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
        lap = (sliding_window_view(g, (3, 3)) * k).sum((-1, -2))
        return float(lap.var())


def folder_census(root, exts: Sequence[str] = (".jpg", ".jpeg", ".png", ".bmp",
                                               ".tif", ".tiff", ".webp")):
    """Images per class per split from an ImageFolder-style tree
    ``root/split/class/*.ext`` -- the first audit artifact for image data.

    Also returns ``missing_class_folders``: classes present in one split but
    absent in another. This matters beyond coverage: folder-derived label
    mappings (torchvision ``ImageFolder.class_to_idx``) are built per split,
    so a missing class folder silently SHIFTS every later class index --
    verify mapping consistency with
    ``engineer-select-eda-features/readiness_check.label_mapping_consistency``.
    """
    import pandas as pd
    from pathlib import Path

    root = Path(root)
    counts: dict[str, dict[str, int]] = {}
    for split_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
            n = sum(1 for f in class_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in exts)
            counts.setdefault(class_dir.name, {})[split_dir.name] = n
    table = pd.DataFrame(counts).T.fillna(0).astype(int).sort_index()
    table.index.name = "class"
    missing = {split: sorted(table.index[table[split] == 0])
               for split in table.columns if (table[split] == 0).any()}
    table.attrs["missing_class_folders"] = missing
    return table


__all__ = [
    "profile_images", "resolution_summary", "channel_stats",
    "average_hash", "near_duplicate_pairs", "blur_score", "folder_census",
]
