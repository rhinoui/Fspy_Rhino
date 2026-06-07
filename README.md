# Fspy_Rhino

Import [fSpy](https://fspy.io/) camera data into [Rhino](https://www.rhino3d.com/).

This script reads an fSpy JSON file and applies the reconstructed camera — position, orientation, focal length, and principal-point shift — to the active Rhino viewport, then saves the result as a named view.

## Why

fSpy is a popular tool for reconstructing 3D cameras from 2D images, but it only natively exports to Blender. This script fills the gap for Rhino users who need accurate camera match in their modeling workflow.

## Features

- Parse fSpy JSON camera transform (position, rotation, focal length)
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

1. Download or clone this repository
2. In Rhino, run the script via one of these methods:

   **Method A — Rhino Python Editor:**
   ```
   _EditPythonScript → File → Open → rhino_paste_fspy.py → Run
   ```

   **Method B — Drag & Drop:**
   Drag `rhino_paste_fspy.py` onto the Rhino window (may require enabling script execution in Rhino options)

   **Method C — Alias / Toolbar Button:**
   ```
   ! _-RunPythonScript "full/path/to/rhino_paste_fspy.py"
   ```

## Usage

1. Open fSpy, load your reference image, and adjust the vanishing points / horizon
2. Export the project: **File → Save** (produces a JSON file with no extension, or `.json`)
3. In Rhino, run the script
4. A file dialog appears — select the fSpy JSON file
5. The active viewport camera is updated and a named view `fSpy_Sync` is saved

### Named View Handling

If a named view `fSpy_Sync` already exists:

| Option | Result |
|---|---|
| **Yes** | Overwrite the existing named view |
| **No** | Save as `fSpy_Sync_2`, `fSpy_Sync_3`, ... |
| **Cancel** | Apply camera without saving a named view |

## fSpy Setup Notes

Make sure fSpy is configured with **Y-up** coordinate system (the default). This matches Rhino's coordinate system directly — no axis conversion is needed.

## Coordinate System Reference

| Axis | fSpy (Y-up) | Rhino |
|---|---|---|
| Right | +X | +X |
| Forward | -Z (camera look) | +Y |
| Up | +Y | +Z |

## License

MIT
