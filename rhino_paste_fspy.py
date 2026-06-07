# -*- coding: utf-8 -*-
"""
rhino_paste_fspy.py -- Import fSpy camera into Rhino

Reads an fSpy JSON file and applies the reconstructed camera
(position, orientation, focal length, principal-point shift)
to the active Rhino viewport, then saves the result as a named view.

fSpy coordinate system (default, Y-up):
    Camera looks down -Z in local space
    Y is up
    X is right

cameraTransform is a 4x4 column-major matrix:
    col 0 = camera right   (X axis)
    col 1 = camera up      (Y axis)
    col 2 = camera forward (-Z axis; view direction is negative of this)
    col 3 = camera position

Rhino coordinate system:
    X = right, Y = forward, Z = up
    No additional axis conversion needed when fSpy is set to Y-up.
"""

import Rhino
import System.Drawing
import json
import math
import Eto.Forms as forms


def load_fspy_json():
    """Open a file dialog, parse an fSpy JSON, and apply the camera to Rhino."""

    # --- Select fSpy JSON file ---
    dlg = forms.OpenFileDialog()
    dlg.Title  = "Select fSpy file"
    dlg.Filters.Add(forms.FileFilter("All files", ".*"))

    if dlg.ShowDialog(None) != forms.DialogResult.Ok:
        return

    filepath = dlg.FileName

    # Accept files with no extension (raw fSpy exports) or .json only
    import os
    ext = os.path.splitext(filepath)[1].lower()
    if ext != "" and ext != ".json":
        Rhino.RhinoApp.WriteLine(
            "Unsupported file type '" + ext
            + "'. Please select a .json or fSpy file with no extension."
        )
        return

    # --- Parse JSON ---
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except Exception as e:
        Rhino.RhinoApp.WriteLine("Failed to read file: " + str(e))
        return

    if "cameraTransform" not in data:
        Rhino.RhinoApp.WriteLine("Not a valid fSpy JSON file.")
        return

    # --- Extract camera transform (row-major 4x4) ---
    rows = data["cameraTransform"]["rows"]
    # rows[row][col]

    # Position = last column
    px, py, pz = rows[0][3], rows[1][3], rows[2][3]

    # Right vector = first column
    rx, ry, rz = rows[0][0], rows[1][0], rows[2][0]

    # Up vector = second column
    ux, uy, uz = rows[0][1], rows[1][1], rows[2][1]

    # Forward vector = negative of third column (camera looks down -Z)
    fx, fy, fz = -rows[0][2], -rows[1][2], -rows[2][2]

    # --- Image dimensions ---
    img_w = data.get("imageWidth",  1920)
    img_h = data.get("imageHeight", 1080)

    # --- Focal length from horizontal FOV ---
    # fSpy stores horizontal FOV in radians; convert to 35 mm equivalent
    h_fov = data.get("horizontalFieldOfView", 1.0)
    lens_blender = 18.0 / math.tan(h_fov / 2.0)   # 36 mm sensor half-width = 18 mm

    # --- Principal point -> shift (Blender shift convention) ---
    pp = data.get("principalPoint", {"x": 0.0, "y": 0.0})
    pp_x = pp.get("x", 0.0)
    pp_y = pp.get("y", 0.0)
    image_aspect = float(img_w) / float(img_h)

    x_shift_scale = 1.0
    y_shift_scale = 1.0
    if img_h > img_w:   # portrait
        x_shift_scale = float(img_w) / float(img_h)
    else:               # landscape
        y_shift_scale = float(img_h) / float(img_w)

    if image_aspect <= 1.0:  # portrait
        pp_rel_x = 0.5 * (pp_x / image_aspect + 1.0)
        pp_rel_y = 0.5 * (-pp_y + 1.0)
    else:                    # landscape
        pp_rel_x = 0.5 * (pp_x + 1.0)
        pp_rel_y = 0.5 * (-pp_y * image_aspect + 1.0)

    shift_x = x_shift_scale * (0.5 - pp_rel_x)
    shift_y = y_shift_scale * (-0.5 + pp_rel_y)

    # --- Apply camera to Rhino ---
    doc   = Rhino.RhinoDoc.ActiveDoc
    scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, doc.ModelUnitSystem)

    loc = Rhino.Geometry.Point3d(px * scale, py * scale, pz * scale)
    fwd = Rhino.Geometry.Vector3d(fx, fy, fz)
    up  = Rhino.Geometry.Vector3d(ux, uy, uz)

    # Set render resolution to match fSpy image
    settings = doc.RenderSettings
    settings.UseViewportSize = False
    settings.ImageSize = System.Drawing.Size(img_w, img_h)
    doc.RenderSettings = settings

    # Lens conversion (Blender -> Rhino 35 mm lens)
    if img_w > img_h:
        lens_rhino = lens_blender * (float(img_w) / float(img_h)) * (2.0 / 3.0)
    else:
        lens_rhino = lens_blender * (2.0 / 3.0)

    view     = doc.Views.ActiveView
    viewport = view.ActiveViewport

    if not viewport.IsPerspectiveProjection:
        viewport.ChangeToPerspectiveProjection(True, lens_rhino)
    viewport.Camera35mmLensLength = lens_rhino

    vp_info = Rhino.DocObjects.ViewportInfo(viewport)
    vp_info.SetCameraLocation(loc)
    vp_info.SetCameraDirection(fwd)
    vp_info.SetCameraUp(up)
    vp_info.Camera35mmLensLength = lens_rhino

    # --- Frustum with principal-point shift ---
    f_near    = 1.0
    f_far     = 1000.0
    vp_aspect = float(viewport.Size.Width) / float(viewport.Size.Height)
    half_h    = f_near * 12.0 / lens_rhino
    half_w    = half_h * vp_aspect
    offset_x  = shift_x * 36.0 / lens_blender
    offset_y  = shift_y * 36.0 / lens_blender

    vp_info.SetFrustum(
        -half_w + offset_x,
         half_w + offset_x,
        -half_h + offset_y,
         half_h + offset_y,
        f_near, f_far
    )

    viewport.SetViewProjection(vp_info, False)

    # Enable safe frame for visual reference
    settings = doc.RenderSettings
    sf = settings.SafeFrame
    sf.Enabled     = True
    sf.LiveFrameOn = True
    doc.RenderSettings = settings

    view.Redraw()

    # --- Save as named view ---
    view_name = "fSpy_Sync"
    existing_index = -1
    for i in range(doc.NamedViews.Count):
        if doc.NamedViews[i].Name == view_name:
            existing_index = i
            break

    if existing_index >= 0:
        import Eto.Forms as etoforms
        result = etoforms.MessageBox.Show(
            "'" + view_name + "' already exists.\n\n"
            "Yes    : Overwrite\n"
            "No     : Save as new (fSpy_Sync_2 ...)\n"
            "Cancel : Sync without saving",
            "Save Named View",
            etoforms.MessageBoxButtons.YesNoCancel
        )
        if result == etoforms.DialogResult.Yes:
            doc.NamedViews.Delete(existing_index)
            doc.NamedViews.Add(view_name, viewport.Id)
        elif result == etoforms.DialogResult.No:
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
        "fSpy synced: " + view_name
        + "  lens=" + str(round(lens_blender, 1)) + "mm"
        + "  shift=(" + str(round(shift_x, 3)) + ", " + str(round(shift_y, 3)) + ")"
        + "  res=" + str(img_w) + "x" + str(img_h)
    )


if __name__ == "__main__":
    load_fspy_json()
