# Parking Map Editor

Create and edit parking-space polygons against a fixed-camera reference frame.
Polygons are stored as JSON and validated before save (positive area, in-bounds
coordinates, unique ids, and no self-crossing edges).

## Quick start

```bash
uv run smart-parking edit-spaces \
  --source data/reference.jpg \
  --output configs/spaces.json \
  --camera-id lot-a-camera-01
```

Reload an existing map (optionally scaling it to the reference frame resolution):

```bash
uv run smart-parking edit-spaces \
  --source data/reference.jpg \
  --output configs/spaces.json \
  --existing configs/parking_spaces.example.json
```

Use `--no-scale-to-source` to keep the existing map's reference resolution when it
differs from the source image or video frame.

## Mouse and keyboard controls

| Input | Action |
| --- | --- |
| Left mouse button | Add a vertex to the active space (auto-starts `S1`, `S2`, … if none is active) |
| `u` | Undo the last vertex on the active space |
| `n` | Start a new space (prompts for id, label, and optional zone in the terminal) |
| `d` | Delete the active space |
| `e` | Toggle enabled / disabled on the active space |
| `[` / `]` | Select previous / next space |
| `s` | Save a validated parking-map JSON to `--output` |
| `q` / `Esc` | Quit (attempts a final save if the map is already valid) |

Overlay colors:

- Cyan outline — active space
- Green outline — enabled inactive space
- Gray outline — disabled space

## JSON schema (summary)

```json
{
  "camera_id": "lot-a-camera-01",
  "reference_width": 1280,
  "reference_height": 720,
  "spaces": [
    {
      "id": "A1",
      "label": "Space A1",
      "zone": "A",
      "enabled": true,
      "polygon": [[100, 200], [220, 200], [220, 360], [100, 360]]
    }
  ]
}
```

Coordinates are in pixels relative to `reference_width` × `reference_height`.

## Scaling when resolution changes

If you draw polygons on a 1280×720 reference and later process 1920×1080 frames,
scale the map so overlap scoring stays aligned:

```python
from smart_parking.config import load_parking_map
from smart_parking.spaces import scale_parking_map, save_parking_map

parking_map = load_parking_map("configs/spaces.json")
scaled = scale_parking_map(parking_map, target_width=1920, target_height=1080)
save_parking_map(scaled, "configs/spaces_1080p.json")
```

The interactive editor scales an `--existing` map to the source frame by default.

## Headless / CI notes

The OpenCV window requires a desktop display. Automated tests cover the
headless `ParkingMapEditor` API (add/undo/serialize/scale) without a GUI.
Set `SMART_PARKING_FORCE_HEADLESS=1` or run under `CI=true` to force the GUI
path to refuse startup rather than hanging.

## Validation rules

Saves fail (non-zero / error message) when any space:

- has fewer than three vertices;
- has non-positive area (collinear / degenerate);
- is self-intersecting (bow-tie / crossing edges);
- has vertices outside the reference resolution;
- reuses another space's id.

Load the saved file with the same rules:

```bash
uv run python -c "from smart_parking.config import load_parking_map; print(load_parking_map('configs/spaces.json'))"
```
