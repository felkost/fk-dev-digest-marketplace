# Computer-vision EDA

Image data follows the same leakage-safe discipline as the rest of the skills;
it just adds file, geometry, and label specifics. The deliverable is a
**validated image dataset + manifests**, not a trained model. Frozen encoders /
foundation models are allowed only as diagnostic probes.

Read the task type first — it changes what you must check:

- **Classification** — folder-per-class or a CSV of `path -> label`.
- **Detection / segmentation** — COCO/YOLO boxes or masks + class per object.
- **Medical / satellite / microscopy** — strong grouping (patient/scene/tile)
  and domain-shift concerns.

## 1. Inventory and integrity (audit)

- For folder-per-class layouts, start with `image_profile.folder_census`:
  images per class per split in one table, plus classes whose folder is
  missing in some split (see the label-mapping trap in §9).
- Count images; check readability, format (JPEG/PNG/TIFF/DICOM…), truncated or
  corrupt files, and the file-size distribution. Flag, do not auto-delete.
- `image_profile.profile_images` + `resolution_summary` produce this.

## 2. Property distributions (audit)

- Resolution `W x H`, aspect ratio, channels / mode (RGB / grayscale / RGBA /
  CMYK), bit depth, color space, EXIF (device, orientation, capture time).
- Watch for mixed sizes, grayscale stored as 3-channel, stray alpha, rotated
  EXIF, and wildly varying aspect ratios (they bias resizing).

## 3. Pixel and color statistics (audit → engineer)

- **Per-channel mean/std normalization constants must be fitted on TRAIN only**
  (`image_profile.channel_stats`) and applied unchanged to val/test — this is
  the image analog of fitting a scaler on train. **This applies when training
  from scratch.**
- **Transfer-learning exception:** a pretrained encoder expects the
  normalization of *its own* pretraining (e.g. ImageNet mean/std), its input
  size, and its resize interpolation — use the weights' published transforms
  (`torchvision` `weights.transforms()`), **not** statistics fitted on your
  train set. Normalizing a pretrained backbone with your own stats quietly
  degrades every downstream embedding and probe.
- Brightness / contrast / saturation, blur (`blur_score`, variance of the
  Laplacian), over/under-exposure, and per-class color histograms.

### Inference input contract

Record in the dataset card and verify at readiness: **dtype** (uint8 vs
float32), **value range** ([0, 255] vs [0, 1] vs normalized), **channel order
and layout** (RGB/BGR, CHW/HWC), **size + interpolation**. A mismatch raises
no error — the model simply predicts garbage; a single custom image run
through the exact training transform chain is the cheapest end-to-end check.

## 4. Labels

- **Classification:** class balance and examples per class, rare/empty classes,
  label-noise via nearest-neighbours in embedding space, and — critically — any
  **confound between an image property and the label** (one class all high-res,
  or all from one source) which becomes a shortcut.
- **Detection / segmentation:** objects per image, box/mask **size and aspect
  distribution**, tiny objects, out-of-bounds or negative coordinates, area
  coverage, per-class box balance, images with no objects, duplicate/overlapping
  boxes, and mask–image size mismatches.
- **Medical / satellite:** label provenance, inter-annotator disagreement, and
  class prevalence per site / scanner / sensor.

## 5. Duplicates and leakage — image-specific, critical

- **Near-duplicates across splits** via perceptual hash or embeddings
  (`near_duplicate_pairs`); the same or lightly-edited image in both train and
  test inflates scores.
- **Group leakage:** the same patient, scene, video, capture session, or
  geographic tile appearing in more than one split — split by that group key.
- Augmented siblings, burst frames, re-uploads, and (for detection) different
  crops of one image must not cross split boundaries.

## 6. Shortcut / bias / confound

- Backgrounds, watermarks, rulers, hospital tags, borders, JPEG artifacts, or a
  capture device that correlates with the label. Probe test: train a simple
  model on **non-object regions or metadata only**; if it predicts the label,
  you have a shortcut to remove or stratify away, not a real signal.

## 7. Structure via embeddings (discover)

- Frozen self-supervised (DINOv2/3) or CLIP embeddings → UMAP/t-SNE
  clusterability, duplicate/outlier review, label-noise triage, and a
  linear-probe estimate of class separability. Use as a probe, not the final
  model; verify domain shift, preprocessing, resolution, and licensing. See
  `discover-eda-structure/references/diagnostic-representations.md`.
- Bring the embeddings as an `N x D` array (this suite does not compute them) and
  run `discover-eda-structure/scripts/embedding_eda.py`: `near_duplicate_pairs`
  (cross-split leakage), `label_noise_candidates` (kNN disagreement),
  `clusterability`, and `separability_probe`.

## 8. Domain / distribution shift (audit → readiness)

- Compare resolution, color, lighting, device, and source across
  train/val/test/deployment, and prevalence per site — a mismatch is the main
  reason image models fail in production.

## 9. Split and readiness (audit → engineer)

- Split by the **group key** (patient/scene/video/tile), stratify by class where
  possible, and keep val/test at the natural prevalence.
- Fit normalization constants and any learned preprocessing/encoder on **train
  only**; dedup across splits; check class/property parity across splits.
- **Label-mapping consistency:** folder-derived mappings
  (`ImageFolder.class_to_idx`) are rebuilt per split, so a class folder missing
  from one split silently shifts every later index — the same integer means
  different classes in train and test, with no error raised. Persist one
  mapping in the dataset card and verify all splits against it
  (`readiness_check.label_mapping_consistency`).
- **Augmentation is a train-only transform** — label-preserving distortions
  act as regularization (ISLP §10.3.4); val/test stay clean. Plan only
  domain-valid augmentations (do not flip if orientation is meaningful),
  render a **preview grid of augmented samples** as an artifact — an
  augmentation that changes the label or destroys the discriminative cue is
  found by eye in seconds; generative augmentation only with fidelity /
  privacy / memorization gates and siblings never crossing splits.
- Readiness fails on any duplicate/group leakage, non-train-fitted statistics,
  inconsistent label mapping, or undocumented shortcut.

## Per-task quick emphasis

| Task | Extra must-checks |
|---|---|
| Classification | class balance, label-noise, property↔label confound |
| Detection / segmentation | box/mask geometry, tiny objects, coordinate sanity, per-box class balance, empty images |
| Medical / satellite | patient/scene/tile group split, scanner/site domain shift, annotator agreement, per-site prevalence |
