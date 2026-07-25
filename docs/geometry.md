# Geometry and assignment

The geometry engine converts parking polygons and detection footprints to Shapely
geometries, measures overlap, and assigns at most one vehicle to each space.

## Overlap metrics

For vehicle footprint `V` and parking polygon `P`:

```text
intersection_area = area(V ∩ P)
space_overlap     = intersection_area / area(P)
vehicle_overlap   = intersection_area / area(V)
```

Centre and bottom-centre points come from the full detection box. Containment
uses Shapely `covers` so boundary points count as inside.

## Footprint height ratio

Elevated cameras often include background above the vehicle. Set
`geometry.footprint_height_ratio` (default `0.60`) to keep only the lower
fraction of the YOLO box as the vehicle footprint.

## Weighted score

```text
score = w_space * space_overlap
      + w_vehicle * vehicle_overlap
      + w_center * centre_inside
      + w_bottom * bottom_centre_inside
```

Weights and `candidate_score_threshold` live under `geometry` in application
settings (`GeometrySettings`).

## Assignment

1. Optionally scale the parking map to the frame resolution.
2. Score every enabled space against every detection.
3. Drop pairs below `candidate_score_threshold`.
4. Greedy one-to-one selection by descending score; ties break by space ID,
   then detection index.

A single vehicle never occupies multiple spaces in one frame. Hungarian
assignment can replace the greedy step later without changing callers.
