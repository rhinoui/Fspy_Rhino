# -*- coding: utf-8 -*-
"""
fspy2rhino.py -- Import fSpy camera (JSON or .fspy) into Rhino

Supports both:
  - .fspy : binary project file (contains embedded image)
  - .json  : exported camera JSON (no image)

Based on the fSpy-Blender importer logic for focal length and
principal-point shift, ported to Rhino IronPython.

fSpy coordinate system (Y-up, default):
  Camera looks down -Z in local space.
  cameraTransform is a 4x4 row-major matrix:
    col 0 = camera right  (X axis)
    col 1 = camera up     (Y axis)
    col 2 = camera forward(-Z axis; view direction is -col2)
    col 3 = camera position

Rhino coordinate system:
  X = right, Y = forward, Z = up
  No axis conversion needed when fSpy is Y-up.
"""

import Rhino
import System.Drawing
import json
import math
import os
import struct
import tempfile
import Eto.Forms as forms


def load_fspy_project(filepath):
    """
    Parse binary .fspy file format.
    Format (little-endian):
      bytes  0-3   : magic "fspy"
      bytes  4-7   : version (uint32)
      bytes  8-11  : JSON payload size (uint32)
      bytes 12-15  : image payload size (uint32)
      bytes 16..    : JSON bytes (utf-8)
      ...           : image bytes (jpg/png)
    Returns (data_dict, image_path_or_None).
    """
    with open(filepath, "rb") as f:
        magic = f.read(4)
        if magic != b"fspy":
            raise Exception("Invalid fSpy file (bad magic bytes)")

        version    = struct.unpack("<I", f.read(4))[0]
        json_size  = struct.unpack("<I", f.read(4))[0]
        image_size = struct.unpack("<I", f.read(4))[0]

        json_bytes  = f.read(json_size)
        data        = json.loads(json_bytes.decode("utf-8"))

        image_bytes = f.read(image_size)

    # Write embedded image to a temp file so Rhino can load it as wallpaper
    image_path = None
    if image_size > 0:
        image_path = os.path.join(tempfile.gettempdir(), "fspy_wallpaper.jpg")
        with open(image_path, "wb") as img:
            img.write(image_bytes)

    return data, image_path


def load_fspy_json():
    """
    Main entry point:
      1. Show file dialog (accept .fspy, .json, or no extension)
      2. Parse camera data
      3. Apply camera to the active Rhino viewport
      4. Optionally set background wallpaper (.fspy only)
      5. Save as a named view
    """
    dlg = forms.OpenFileDialog()
    dlg.Title = "Select fSpy file"
    dlg.Filters.Add(forms.FileFilter("fSpy Project", ".fspy"))
    dlg.Filters.Add(forms.FileFilter("JSON export", ".json"))
    dlg.Filters.Add(forms.FileFilter("All files",    ".*"))

    if dlg.ShowDialog(None) != forms.DialogResult.Ok:
        return

    filepath = dlg.FileName
    ext = os.path.splitext(filepath)[1].lower()

    # Accept: .fspy (binary), .json (export), or no extension (fspy save)
    if ext not in [".json", ".fspy", ""]:
        Rhino.RhinoApp.WriteLine("Unsupported file type: " + ext)
        return

    image_path = None
    try:
        if ext == ".fspy":
            # Binary format: extract JSON + embedded image
            data, image_path = load_fspy_project(filepath)
            # .fspy wraps camera data under "cameraParameters"
            if "cameraParameters" in data:
                data = data["cameraParameters"]
        else:
            # Plain JSON export: camera data is top-level
            with open(filepath, "r") as f:
                data = json.load(f)
    except Exception as e:
        Rhino.RhinoApp.WriteLine("Failed to read file: " + str(e))
        return

    if "cameraTransform" not in data:
        Rhino.RhinoApp.WriteLine("No cameraTransform found in file.")
        return

    # --- Extract camera transform (row-major 4x4) ---
    # rows[row][col] -> col3 = position, col0 = right, col1 = up
    rows = data["cameraTransform"]["rows"]
    px, py, pz = rows[0][3], rows[1][3], rows[2][3]
    ux, uy, uz = rows[0][1], rows[1][1], rows[2][1]
    # Camera looks down -Z, so forward = -col2
    fx, fy, fz = -rows[0][2], -rows[1][2], -rows[2][2]

    # --- Image dimensions (for render resolution + aspect) ---
    img_w = data.get("imageWidth",  1920)
    img_h = data.get("imageHeight", 1080)

    # --- Focal length from horizontal FOV ---
    # fSpy stores H-FOV in radians; 36 mm is the full sensor width
    h_fov     = data.get("horizontalFieldOfView", 1.0)
    lens_fspy = 18.0 / math.tan(h_fov / 2.0)   # half-sensor = 18 mm

    # --- Principal point -> Blender-style shift ---
    # (Ported from fSpy-Blender importer: fspy_blender/importer.py)
    pp       = data.get("principalPoint", {"x": 0.0, "y": 0.0})
    pp_x     = pp.get("x", 0.0)
    pp_y     = pp.get("y", 0.0)
    img_aspect = float(img_w) / float(img_h)

    x_shift_scale = 1.0
    y_shift_scale = 1.0
    if img_h > img_w:   # portrait
        x_shift_scale = float(img_w) / float(img_h)
    else:                # landscape
        y_shift_scale = float(img_h) / float(img_w)

    if img_aspect <= 1.0:  # portrait
        pp_rel_x = 0.5 * (pp_x / img_aspect + 1.0)
        pp_rel_y = 0.5 * (-pp_y + 1.0)
    else:                  # landscape
        pp_rel_x = 0.5 * (pp_x + 1.0)
        pp_rel_y = 0.5 * (-pp_y * img_aspect + 1.0)

    shift_x = x_shift_scale * (0.5 - pp_rel_x)
    shift_y = y_shift_scale * (-0.5 + pp_rel_y)

    # --- Unit handling ---
    # fSpy camera matrix is always in metres, regardless of the UI unit
    # selector. UnitScale converts metres to the current Rhino model unit.
    doc   = Rhino.RhinoDoc.ActiveDoc
    scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters,
                                        doc.ModelUnitSystem)

    loc = Rhino.Geometry.Point3d(px * scale, py * scale, pz * scale)
    fwd = Rhino.Geometry.Vector3d(fx, fy, fz)
    up  = Rhino.Geometry.Vector3d(ux, uy, uz)

    # --- Apply render resolution ---
    settings = doc.RenderSettings
    settings.UseViewportSize = False
    settings.ImageSize = System.Drawing.Size(img_w, img_h)
    doc.RenderSettings = settings

    # --- Lens length conversion ---
    # Empirical formula verified against Blender sync; the 2/3 factor
    # maps Blender 35 mm lens to Rhino's lens units.
    if img_w > img_h:
        lens_rhino = lens_fspy * (float(img_w) / float(img_h)) * (2.0 / 3.0)
    else:
        lens_rhino = lens_fspy * (2.0 / 3.0)

    view     = doc.Views.ActiveView
    viewport = view.ActiveViewport

    if not viewport.IsPerspectiveProjection:
        viewport.ChangeToPerspectiveProjection(True, lens_rhino)
    viewport.Camera35mmLensLength = lens_rhino

    # --- Build ViewportInfo with frustum + principal-point shift ---
    vp_info   = Rhino.DocObjects.ViewportInfo(viewport)
    vp_info.SetCameraLocation(loc)
    vp_info.SetCameraDirection(fwd)
    vp_info.SetCameraUp(up)
    vp_info.Camera35mmLensLength = lens_rhino

    f_near    = 1.0
    f_far     = 1000.0
    vp_aspect = float(viewport.Size.Width) / float(viewport.Size.Height)
    half_h    = f_near * 12.0 / lens_rhino
    half_w    = half_h * vp_aspect

    # Shift the frustum to match the fSpy principal point offset
    offset_x  = shift_x * 36.0 / lens_fspy
    offset_y  = shift_y * 36.0 / lens_fspy

    vp_info.SetFrustum(
        -half_w + offset_x,   half_w + offset_x,
        -half_h + offset_y,   half_h + offset_y,
        f_near, f_far
    )

    viewport.SetViewProjection(vp_info, False)

    # --- Set wallpaper (only available with .fspy binary) ---
    if image_path and os.path.exists(image_path):
        try:
            # SetWallpaper(filename, grayscale=False) for colour image
            viewport.SetWallpaper(image_path, False)
        except Exception as e:
            Rhino.RhinoApp.WriteLine("Wallpaper failed: " + str(e))

    # --- Enable safe frame for visual alignment ---
    settings = doc.RenderSettings
    sf = settings.SafeFrame
    sf.Enabled     = True
    sf.LiveFrameOn = True
    doc.RenderSettings = settings

    view.Redraw()

    # --- Save / overwrite Named View ---
    view_name     = "fSpy_Sync"
    existing_index = -1
    for i in range(doc.NamedViews.Count):
        if doc.NamedViews[i].Name == view_name:
            existing_index = i
            break

    if existing_index >= 0:
        result = forms.MessageBox.Show(
            "'" + view_name + "' already exists.\n\n"
            "Yes    : Overwrite\n"
            "No     : Save as new (fSpy_Sync_2 ...)\n"
            "Cancel : Sync without saving",
            "Save Named View",
            forms.MessageBoxButtons.YesNoCancel
        )
        if result == forms.DialogResult.Yes:
            doc.NamedViews.Delete(existing_index)
            doc.NamedViews.Add(view_name, viewport.Id)
        elif result == forms.DialogResult.No:
            index = 2
            while True:
                new_name = view_name + "_" + str(index)
                exists = any(
                    doc.NamedViews[i].Name == new_name
                    for i in range(doc.NamedViews.Count)
                )
                if not exists:
                    doc.NamedViews.Add(new_name, viewport.Id)
                    view_name = new_name
                    break
                index += 1
    else:
        doc.NamedViews.Add(view_name, viewport.Id)

    Rhino.RhinoApp.WriteLine(
        "fSpy synced: " + view_name +
        "  lens=" + str(round(lens_fspy, 1)) + "mm" +
        "  shift=(" + str(round(shift_x, 3)) + ", " + str(round(shift_y, 3)) + ")" +
        "  res=" + str(img_w) + "x" + str(img_h)
    )


if __name__ == "__main__":
    load_fspy_json()
