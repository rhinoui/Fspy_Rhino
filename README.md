# Fspy_Rhino

Import [fSpy](https://fspy.io/) camera data into [Rhino](https://www.rhino3d.com/).

This script reads an fSpy JSON file and applies the reconstructed camera — position, orientation, focal length, and principal-point shift — to the active Rhino viewport, then saves the result as a named view.

## Why

fSpy is a popular tool for reconstructing 3D cameras from 2D images.  
The official workflow only supports Blender (via [fSpy-Blender](https://github.com/stuffmatic/fSpy-Blender)), leaving Rhino users without a native solution. This script fills that gap.

## Credits & References

- **[fSpy](https://fspy.io/)** — The camera matching application this script reads from.
- **[fSpy-Blender](https://github.com/stuffmatic/fSpy-Blender)** — The official Blender importer. This project's focal-length and principal-point shift math is adapted from its source code (`fspy_blender/importer.py`), ported from Blender Python API to Rhino IronPython.
- **Coordinate system note:** fSpy outputs a Y-up camera transform. Both Blender and Rhino use Y-up, so no axis-swap is needed — the same transform matrix logic works for both.

## Features

- Parse fSpy JSON camera transform (position, orientation, focal length)
- Compute principal-point shift and apply via Rhino frustum offset
- Automatically set render resolution to match the source image
- Save camera as a named view (with overwrite / rename dialog)
- Enable Rhino safe frame for visual alignment reference

## Requirements

| Requirement | Notes |
|---|---|
| Rhino 6+ | Tested on Rhino 7 / 8 |
| IronPython | Built-in with Rhino (no separate install) |
| fSpy | [Download here](https://fspy.io/) |

**No pip dependencies** — the script only uses Python standard library (`json`, `math`, `os`) and Rhino/.NET built-in modules (`Rhino`, `System.Drawing`, `Eto.Forms`).

## Installation

1. Download or clone this repository.
2. Place `rhino_paste_fspy.py` in a stable location (e.g. `C:/Users/YourName/RhinoScripts/`).
3. In Rhino, run the script via one of these methods:

   **Method A — Rhino Python Editor:**
   ```
   _EditPythonScript → File → Open → select rhino_paste_fspy.py → Run
   ```

   **Method B — Drag & Drop:**
   Drag `rhino_paste_fspy.py` onto the Rhino window (may require enabling script execution in Rhino options).

   **Method C — Toolbar Button / Alias (recommended):**
   Create a toolbar button with this command (replace the path with your own):
   ```
   ! _-RunPythonScript "E:/Rhinoceros/Plugin/Cam_Sync/rhino_paste_fspy.py"
   ```
   > **Note:** Rhino on Windows accepts forward slashes (`/`) in paths.  
   > If you prefer backslashes, double them: `"E:\\Rhinoceros\\Plugin\\Cam_Sync\\rhino_paste_fspy.py"`

## Usage

1. Open fSpy, load your reference image, and adjust the vanishing points / horizon.
2. Export the project: **File → Save** (produces a file with no extension, or `.json`).
3. In Rhino, run the script (via any method above).
4. A file dialog appears — select the fSpy JSON file.
5. The active viewport camera is updated and a named view `fSpy_Sync` is saved.

### Named View Handling

If a named view `fSpy_Sync` already exists:

| Option | Result |
|---|---|
| **Yes** | Overwrite the existing named view |
| **No** | Save as `fSpy_Sync_2`, `fSpy_Sync_3`, ... |
| **Cancel** | Apply camera without saving a named view |

## fSpy Setup Notes

Make sure fSpy is configured with **Y-up** coordinate system (the default). This matches Rhino's coordinate system directly — no axis conversion is needed.

### ⚠️ Unit Input Rule (Important)

Due to a design limitation in fSpy, the **unit dropdown** in the interface (mm / cm / m) does **not** affect the exported camera matrix — it is always exported in unitless absolute values. To ensure the camera position in Rhino matches your model dimensions precisely, you **must** follow this rule:

> **Always treat the Reference Distance input as meters, regardless of what the dropdown shows.**

| Actual Measurement | fSpy Input |
|---|---|
| 800 mm | `0.8` |
| 20 mm | `0.02` |
| 2 m | `2` |

**Why this works:** The Rhino script uses `UnitScale` to automatically read your current Rhino document's unit system (mm, cm, m, etc.) and convert the meter-based data from fSpy to the correct scale for your scene. As long as you input the reference distance in meters, the import will be 1:1 accurate.

## Coordinate System Reference

| Axis | fSpy (Y-up) | Rhino |
|---|---|---|
| Right | +X | +X |
| Forward | -Z (camera look direction) | +Y |
| Up | +Y | +Z |

## Troubleshooting

- **"Not a valid fSpy JSON file"** — Make sure you exported via *File → Save* in fSpy, not *Export for Blender*.
- **Camera looks wrong** — Verify fSpy's camera transform in *View → Show Camera*. The matrix should be Y-up.
- **Script doesn't run** — Check that Rhino's Python editor is enabled (*Tools → Options → Python*).

## License

MIT
