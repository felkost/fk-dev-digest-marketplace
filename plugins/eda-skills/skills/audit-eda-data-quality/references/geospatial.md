# Geospatial EDA

Geodata follows the same leakage-safe discipline as the rest of the skills; it
adds coordinate-system, geometry, and spatial-dependence specifics. The
deliverable is a **validated geospatial dataset + manifests**, not a trained
model or a map product.

Read the data model first — it changes what you must check:

- **Points** — events, sensors, geocoded addresses (`lat/lon` columns or Point
  geometries).
- **Areal / polygons** — admin units, parcels, zones with attributes per unit.
- **Raster / tiles** — satellite or aerial chips; combine with
  `references/computer-vision.md` for the image side.
- **Trajectories** — GPS tracks: ordered points per entity over time; combine
  with `discover-eda-structure/references/time-series.md` for the temporal side.

## 1. CRS and coordinate sanity (audit)

- Every layer must have a **declared CRS**; a missing or assumed CRS is a
  defect to flag, not to guess silently. Record source and working CRS in the
  dataset contract.
- Geographic CRS (degrees, e.g. EPSG:4326) vs projected CRS (meters): compute
  **distance, area, and buffers only in a suitable projected CRS** (local UTM
  zone; equal-area for areas). Meters-from-raw-degrees is the classic silent
  error — 1° of longitude shrinks with latitude by cos(lat).
- Axis order: `lat/lon` vs `lon/lat` swaps produce points in the wrong
  hemisphere. Cheap check: plot the bounding box against the expected study
  area.
- Mixed CRS across sources: reproject everything to one working CRS **before**
  any join or distance computation; datum differences (WGS84 vs local datums)
  cause systematic offsets of tens–hundreds of meters.

## 2. Coordinate validity and sentinels (audit)

- Range checks: lat ∈ [−90, 90], lon ∈ [−180, 180]; out-of-study-area points;
  suspected lat/lon swaps (values valid globally but outside the study bbox).
- **Sentinel coordinates:** (0, 0) "Null Island", (90, 0), a country/city
  centroid or office HQ repeated thousands of times — geocoder fallbacks, not
  locations. Detect via frequency spikes at exact repeated coordinates.
- Precision heaping: coordinates rounded to 2–3 decimals snap to a grid
  (~1–11 km); mixed geocoding quality tiers (rooftop vs street vs centroid)
  must be kept as an explicit quality flag, never silently mixed.
- Trajectories: impossible speeds (teleporting GPS), zero-movement runs,
  duplicated timestamps, gaps; flag and segment, do not auto-smooth.

## 3. Geometry validity (audit; vector data)

- Invalid polygons: self-intersections, unclosed rings, wrong winding order —
  `is_valid` + `explain_validity`, repair with `make_valid` **explicitly and
  log the change**; do not auto-drop invalid rows.
- Empty geometries, zero-area polygons, sliver polygons left over from overlay
  operations.
- Mixed geometry types in one layer (Point + Polygon together is suspicious;
  Polygon + MultiPolygon is normal).
- Topology of layers that should tile space (admin units): overlaps and gaps
  between neighbors; compare area sums against official totals.

## 4. Spatial joins and aggregation units (audit)

- Point-in-polygon joins: CRS must match first; count points that match **no**
  polygon (coastal/offshore/boundary points) and flag them — a silent inner
  join deletes them.
- Overlapping polygons make spatial joins many-to-many: check row counts
  before/after, as with any join.
- **MAUP (modifiable areal unit problem):** the same data aggregated to
  different units gives different rates and correlations — record the chosen
  unit as a modeling decision. Area-level associations do not transfer to
  individuals (ecological fallacy); mark such conclusions as area-level.

## 5. Spatial coverage and sampling bias (audit)

- Density map / hexbin of observations: data concentrates where people and
  sensors are, not uniformly; per-region counts and target rates obey the same
  small-group discipline as elsewhere (`group_rate_funnel` — tiny regions land
  on both extremes of any rate ranking by chance).
- Coverage vs deployment region: empty regions are extrapolation zones — name
  them in the report.
- Edge effects: neighborhood features are truncated at the study-area
  boundary; flag boundary observations.

## 6. Spatial autocorrelation (audit → discover)

- Tobler's law: near things are more alike. Measure it instead of assuming:
  global Moran's I on target and key features; a semivariogram to estimate the
  **autocorrelation range** (distance at which similarity fades); local Moran
  (LISA) for hot/cold spots.
- This is not cosmetic: positive autocorrelation means a random row split
  leaks — a test point surrounded by train points is nearly a duplicate of
  them.
- Report the estimated range: it sets the buffer distance for split design
  (§7) and the neighborhood radius for features (§8).

## 7. Spatial leakage and split design (audit) — critical

- Random row split on autocorrelated data inflates scores; treat it like
  duplicate leakage.
- **Spatial block CV:** assign contiguous blocks (H3 cells, grid squares,
  admin regions) as the group key so neighbors stay in one fold
  (`split_designer.py` with `strategy="spatial"`, region id as `group`).
- **Buffered CV:** additionally exclude a buffer ring (≥ the autocorrelation
  range from §6) around each test block from train — neighbors just across a
  block edge are still near-duplicates.
- Repeated observations of one location over time → group key = location id;
  add a chronological split when the task is forecasting.
- Raster chips: overlapping chips of one scene/tile must not cross splits —
  same rule as image near-duplicates; group by scene/tile id.
- If the goal is generalization to **new** regions, hold out whole regions and
  report metrics per region, not only pooled.

## 8. Geo features — fit on train only (engineer)

- **H3/geohash cell aggregates:** cell id at a documented resolution as a
  categorical key; per-cell counts/means are learned statistics — fit on
  train/fold, persist the mapping; target-based cell rates only via OOF
  target-encoding. Unseen or rare cells fall back to the parent (coarser)
  resolution or the global value — record the threshold.
- k-ring neighborhood aggregates and distance-to-POI features (city center,
  road, coast): compute in a projected CRS; the POI snapshot must be
  point-in-time — a POI database newer than the observations leaks the future.
- Raw lat/lon as features: trees split on them effectively, but this binds the
  model to the mapped region and encodes region identity — a deliberate,
  documented choice, not a default; distances/relative coordinates generalize
  differently.
- Areas and lengths as features: recompute in an equal-area/equidistant
  projection, not in degrees.

## 9. Domain shift and readiness

- Compare feature and target distributions across regions; train region ≠
  deployment region is the geo analog of device/site shift in images.
- Readiness fails on: undeclared or mixed CRS, silently dropped invalid
  geometries, a random split despite measured autocorrelation, cell aggregates
  fitted on all data, or train points inside the buffer of a test block.

## Per-task quick emphasis

| Data model | Extra must-checks |
|---|---|
| Points (events/sensors) | sentinel coordinates, geocode precision tiers, sampling-density bias, block+buffer split |
| Areal / polygons | topology overlaps/gaps, MAUP, small-region rate traps, region holdout |
| Raster / tiles | chip overlap across splits, scene/tile group key, plus all of computer-vision.md |
| Trajectories | impossible speeds/gaps, split by entity (vehicle/user), joint space+time leakage |
