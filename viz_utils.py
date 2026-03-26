import os
import csv
import json
from typing import Dict, Optional, Tuple, List, Set

from .fnx_api import FNXApi
from .fnx_io_definition import OutputDefinition
import omni.usd
from pxr import Usd, UsdGeom, Gf, Vt, Sdf, UsdLux, UsdShade


# pxr is available in Omniverse for USD ops
try:
    import matplotlib.cm as cm
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    import numpy as np
    import io
    from matplotlib.ticker import MaxNLocator 
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


print(f"[DEBUG] Matplotlib available: {MATPLOTLIB_AVAILABLE}")
print(f"[DEBUG] Pillow available: {PILLOW_AVAILABLE}")


# Expose available colormaps for UI

COLOR_MAP_OPTIONS = [
    # Perceptually Uniform Sequential
    "viridis", "plasma", "inferno", "magma", "cividis",
    # Sequential
    "Blues", "Greens", "Reds",
    # Diverging (good for showing positive and negative deviation)
    "coolwarm", "bwr", "seismic",
    # Classic (use with caution)
    "jet", "rainbow",
    # Grayscale
    "gray"
]


def get_visualizable_properties():
    """Returns a list of properties that can be visualized."""
    return [
        "Temperature", "Pressure", "Quality", "Velocity",
        "Volume Flow Rate", "Mass Flux",
    ]

# ---------------------------------------------------------------------------
# Visualization session-layer state
# ---------------------------------------------------------------------------
# Path for the temporary material scope created inside the session layer.
_VIZ_SCOPE_PATH = "/_VizMaterials"

# Fallback material applied to prims when no output data is available.
_FALLBACK_MATERIAL_PATH = "/World/Looks/Aluminum_Foil"

# Tracks which prim paths have had a material-binding override written to the
# session layer so that _reset_prim_colors can remove exactly those overrides
# (and nothing else) without touching the rest of the session layer.
_viz_session_overrides: Set[str] = set()


_GEO_TYPE_NAMES: frozenset = frozenset({
    "Mesh", "BasisCurves", "Points", "NurbsPatch",
    "Capsule", "Cone", "Cube", "Cylinder", "Sphere",
})


def _collect_geometry_prims(prim: Usd.Prim) -> List[Usd.Prim]:
    """
    Traverse *prim* and all its descendants and return every active, defined
    geometry prim (Mesh, BasisCurves, etc.) found.

    If *prim* is itself a geometry prim, returns ``[prim]`` without further
    traversal.  This is used to find the actual renderable prims so that
    material bindings can be written directly on them, without needing any
    ``strongerThanDescendants`` / ``weakerThanDescendants`` override.
    """
    result: List[Usd.Prim] = []
    for p in Usd.PrimRange(prim):
        if not p.IsActive() or not p.IsDefined():
            continue
        if p.GetTypeName() in _GEO_TYPE_NAMES:
            result.append(p)
    return result


def _find_prims_by_flownex_name(
    stage: Usd.Stage, component_id: str, root: str = "/World"
) -> List[Usd.Prim]:
    """
    Scan the stage for prims that carry a non-empty ``flownex:componentName``
    attribute whose value matches *component_id*.

    This is the primary target-finding mechanism for visualization.  Any prim
    type (Mesh, Xform, etc.) may be returned.  When the returned prim is not
    itself a geometry prim (e.g. it is an Xform parent), ``_apply_color_to_prim``
    will automatically walk its subtree via ``_collect_geometry_prims`` and bind
    the colour material to every renderable descendant.

    Matching is case-insensitive with whitespace collapsed so that minor
    formatting differences between the CSV identifier and the USD attribute
    value are tolerated.

    Parameters
    ----------
    stage        : the active USD stage.
    component_id : Flownex ComponentIdentifier string to match.
    root         : stage path to start traversal from (default ``"/World"``).

    Returns
    -------
    List[Usd.Prim]
        A (possibly empty) list of matching prims.
    """
    def _norm(s: str) -> str:
        return "".join((s or "").split()).lower()

    target = _norm(component_id)
    result: List[Usd.Prim] = []

    root_prim = stage.GetPrimAtPath(root)
    traverse = (
        Usd.PrimRange(root_prim)
        if root_prim and root_prim.IsValid()
        else stage.Traverse()
    )
    for prim in traverse:
        if not prim.IsActive() or not prim.IsDefined() or prim.IsInstanceProxy():
            continue
        attr = prim.GetAttribute("flownex:componentName")
        if not attr or not attr.IsValid():
            continue
        val = attr.Get()
        if val and _norm(str(val)) == target:
            result.append(prim)
    return result


def _apply_color_to_prim(stage: Usd.Stage, prim: Usd.Prim, rgb: Tuple[float, float, float]) -> int:
    """
    Applies a visualization colour to *prim* and all its geometry descendants
    via the session layer.

    Implementation
    --------------
    * All edits go to the **session layer** so they are never persisted to disk.
    * For every geometry prim (Mesh, etc.) in the subtree a ``UsdPreviewSurface``
      material is bound **directly on the geometry prim** without any binding-
      strength token (``strongerThanDescendants`` / ``weakerThanDescendants``).
      Because the session layer is the strongest layer in the stack the binding
      wins over any root-layer opinion automatically, so no strength override is
      needed and existing binding-strength settings elsewhere in the scene are
      completely undisturbed.
    * For light prims the ``inputs:color`` attribute is set instead.

    Returns the number of prims that received a colour opinion (0 on failure).
    """
    global _viz_session_overrides

    if not prim or not prim.IsValid():
        return 0

    session_layer = stage.GetSessionLayer()
    if not session_layer:
        return 0

    old_target = stage.GetEditTarget()
    stage.SetEditTarget(Usd.EditTarget(session_layer))
    colored_count = 0

    try:
        r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])

        if prim.HasAPI(UsdLux.LightAPI):
            # Lights: override the colour attribute in the session layer.
            try:
                UsdLux.LightAPI(prim).CreateColorAttr().Set(Gf.Vec3f(r, g, b))
                _viz_session_overrides.add(prim.GetPath().pathString)
                colored_count += 1
            except Exception as e:
                print(f"[viz] Light colour override failed on {prim.GetPath()}: {e}")
        else:
            # Geometry / assemblies: bind a UsdPreviewSurface material directly
            # on each geometry prim in the subtree.  No binding-strength token is
            # written – the session layer's higher priority means it always wins
            # without needing to touch any strength attribute.
            mat_key = f"r{int(r * 255):03d}g{int(g * 255):03d}b{int(b * 255):03d}"
            mat_path = Sdf.Path(f"{_VIZ_SCOPE_PATH}/{mat_key}")

            UsdGeom.Scope.Define(stage, _VIZ_SCOPE_PATH)

            if not stage.GetPrimAtPath(mat_path).IsValid():
                mat = UsdShade.Material.Define(stage, mat_path)
                shader = UsdShade.Shader.Define(stage, mat_path.AppendChild("Shader"))
                shader.CreateIdAttr("UsdPreviewSurface")
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                    Gf.Vec3f(r, g, b)
                )
                shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.4)
                shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                mat.CreateSurfaceOutput().ConnectToSource(
                    shader.ConnectableAPI(), "surface"
                )

            mat = UsdShade.Material(stage.GetPrimAtPath(mat_path))

            geo_prims = _collect_geometry_prims(prim)
            if not geo_prims:
                print(f"[viz] No geometry prims found under {prim.GetPath()}; skipping.")
            for geo_prim in geo_prims:
                try:
                    # No binding-strength argument → fallbackStrength is used,
                    # which means the strength attribute is NOT written at all.
                    UsdShade.MaterialBindingAPI.Apply(geo_prim).Bind(mat)
                    _viz_session_overrides.add(geo_prim.GetPath().pathString)
                    colored_count += 1
                except Exception as e:
                    print(f"[viz] Material bind failed on {geo_prim.GetPath()}: {e}")
    finally:
        stage.SetEditTarget(old_target)

    return colored_count


def _apply_fallback_material_to_prim(stage: Usd.Stage, prim: Usd.Prim) -> int:
    """
    Binds the fallback material at ``_FALLBACK_MATERIAL_PATH``
    (``/World/Looks/Aluminum_Foil``) directly on every geometry prim in the
    subtree rooted at *prim*, via the session layer.

    The binding is written without any binding-strength token so that the
    existing ``strongerThanDescendants`` / ``weakerThanDescendants`` settings
    elsewhere in the scene are completely undisturbed.

    If the Aluminum_Foil material is not present in the stage, the function
    falls back to applying a silver colour via ``_apply_color_to_prim``.

    Returns the number of geometry prims bound (0 on failure).
    """
    global _viz_session_overrides

    if not prim or not prim.IsValid():
        return 0

    fallback_mat_prim = stage.GetPrimAtPath(_FALLBACK_MATERIAL_PATH)
    if not fallback_mat_prim or not fallback_mat_prim.IsValid():
        print(f"[viz] Fallback material '{_FALLBACK_MATERIAL_PATH}' not found; using silver.")
        return _apply_color_to_prim(stage, prim, (0.75, 0.75, 0.75))

    session_layer = stage.GetSessionLayer()
    if not session_layer:
        return 0

    old_target = stage.GetEditTarget()
    stage.SetEditTarget(Usd.EditTarget(session_layer))
    colored_count = 0

    try:
        mat = UsdShade.Material(fallback_mat_prim)
        geo_prims = _collect_geometry_prims(prim)
        if not geo_prims:
            print(f"[viz] No geometry prims found under {prim.GetPath()}; skipping fallback bind.")
        for geo_prim in geo_prims:
            try:
                UsdShade.MaterialBindingAPI.Apply(geo_prim).Bind(mat)
                _viz_session_overrides.add(geo_prim.GetPath().pathString)
                colored_count += 1
            except Exception as e:
                print(f"[viz] Fallback material bind failed on {geo_prim.GetPath()}: {e}")
    finally:
        stage.SetEditTarget(old_target)

    return colored_count


def _reset_prim_colors(stage: Usd.Stage, prim_paths: Set[str]):
    """
    Undo all visualization colour overrides written to the session layer by
    previous calls to ``_apply_color_to_prim``.

    The *prim_paths* parameter is kept for API compatibility; the authoritative
    set of paths to clean up is the module-level ``_viz_session_overrides``.
    """
    global _viz_session_overrides

    if not stage:
        return

    session_layer = stage.GetSessionLayer()
    if not session_layer:
        return

    old_target = stage.GetEditTarget()
    stage.SetEditTarget(Usd.EditTarget(session_layer))

    try:
        # Remove the material-binding relationship we authored for each geometry
        # prim and clear any light-colour overrides.
        for path_str in _viz_session_overrides:
            prim = stage.GetPrimAtPath(path_str)
            if not prim or not prim.IsValid():
                continue
            # Clear material binding written by _apply_color_to_prim /
            # _apply_fallback_material_to_prim.
            rel = UsdShade.MaterialBindingAPI(prim).GetDirectBindingRel()
            if rel and rel.IsValid():
                # ClearTargets(True) removes the relationship spec from the
                # current edit target, restoring the weaker-layer binding.
                rel.ClearTargets(True)
            # For lights, clear the colour attribute override.
            if prim.HasAPI(UsdLux.LightAPI):
                color_attr = prim.GetAttribute("inputs:color")
                if color_attr and color_attr.IsValid():
                    color_attr.Clear()

        # Remove the entire /_VizMaterials scope from the session layer so
        # there are no leftover material prims.
        viz_prim = stage.GetPrimAtPath(_VIZ_SCOPE_PATH)
        if viz_prim and viz_prim.IsValid():
            stage.RemovePrim(Sdf.Path(_VIZ_SCOPE_PATH))
    finally:
        stage.SetEditTarget(old_target)

    _viz_session_overrides = set()


def color_map(norm: float, cmap: str = "blue-white-red") -> Tuple[float, float, float]:
    """
    Returns an RGB tuple (0..1 floats) based on the normalized value and selected colormap.
    """
    norm = max(0.0, min(1.0, float(norm)))

    if not MATPLOTLIB_AVAILABLE:
        print("[viz] Warning: Matplotlib not found. Falling back to grayscale.")
        return (norm, norm, norm)

    try:
        colormap_func = cm.get_cmap(cmap)
        rgba = colormap_func(norm)
        return rgba[:3]
    except ValueError:
        print(f"[viz] Warning: Colormap '{cmap}' not found. Falling back to 'viridis'.")
        return cm.get_cmap("viridis")(norm)[:3]


def _load_component_to_prim_map(mapping_json_path: str) -> Dict[str, str]:
    """
    Load mapping of { ComponentIdentifier: primPath } from JSON.
    """
    with open(mapping_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Mapping JSON must be an object of {ComponentIdentifier: primPath}")
        return data


def _normalize_prim_paths(paths) -> List[str]:
    """
    Ensure *paths* is always a ``List[str]``.

    Older ``FlownexMapping.json`` files stored prim paths as plain strings
    rather than single-element lists.  This helper normalises both formats so
    callers can always iterate safely.
    """
    if isinstance(paths, str):
        return [paths]
    return list(paths) if paths else []


def _visualize_single_component(
    output_def: OutputDefinition, value: float, comp_to_prim_map: Dict[str, List[str]], 
    property_ranges: Dict[str, Dict[str, float]], cmap: str, usd_context=None,
) -> Dict[str, object]:
    """
    Visualize a single Flownex component by applying a color derived from
    *value* to all relevant USD prims.

    Target-finding strategy
    -----------------------
    1. **Direct stage scan** (primary): the stage is scanned for prims of any
       type whose ``flownex:componentName`` attribute is non-empty and matches
       *component_id*.  If a matching prim is itself a geometry prim it is
       colored directly; if it is an Xform (or other assembly prim)
       ``_apply_color_to_prim`` automatically walks its subtree to color all
       renderable geometry descendants.
    2. **JSON mapping fallback**: if no tagged prims are found via the direct
       scan the pre-built ``comp_to_prim_map`` is consulted and the geometry
       descendants of each stored prim path are colored via
       ``_apply_color_to_prim``.

    The ``"colored_paths"`` list in the returned dict always contains the paths
    of the prims that were actually targeted (tagged prim paths for the direct
    scan, mapping prim paths for the fallback).  Callers use this to determine
    which components received a color so that a fallback "no-data" material can
    be applied to the remainder.
    """
    key = output_def.Key
    component_id = output_def.ComponentIdentifier
    info = { "key": key, "status": "error", "message": "", "colored_prims": 0, "colored_paths": [] }

    pr = property_ranges.get(key)
    if not pr or pr.get("min") is None or pr.get("max") is None:
        info["message"] = "No valid range specified"
        return info

    vmin, vmax = pr["min"], pr["max"]
    norm = (value - vmin) / (vmax - vmin) if (vmax - vmin) > 1e-9 else 0.5
    rgb = color_map(norm, cmap=cmap)

    ctx = usd_context or omni.usd.get_context()
    stage = ctx.get_stage()
    if not stage:
        info["message"] = "USD stage not available"
        return info

    total_colored = 0

    # --- Primary: scan for prims tagged with this component name ---
    tagged_prims = _find_prims_by_flownex_name(stage, component_id)
    if tagged_prims:
        for tagged_prim in tagged_prims:
            colored_count = _apply_color_to_prim(stage, tagged_prim, rgb)
            if colored_count > 0:
                total_colored += colored_count
                info["colored_paths"].append(tagged_prim.GetPath().pathString)
    else:
        # --- Fallback: use the pre-built JSON mapping ---
        prim_paths = comp_to_prim_map.get(component_id)
        if not prim_paths:
            info["message"] = "Not found in stage scan or mapping file"
            return info
        for prim_path in _normalize_prim_paths(prim_paths):
            prim = stage.GetPrimAtPath(prim_path)
            colored_count = _apply_color_to_prim(stage, prim, rgb)
            if colored_count > 0:
                total_colored += colored_count
                info["colored_paths"].append(prim_path)

    info["colored_prims"] = total_colored
    if total_colored > 0:
        info["status"] = "ok"
        info["message"] = f"Colored {total_colored} prims/lights."
    else:
        info["message"] = "No geometry or lights found to color."
        
    return info


def visualize_property_layer(
    log_field, property_combo, colormap_combo, property_names_for_viz, user_config,
    fnx_outputs: List[OutputDefinition], output_fields: Dict[str, str], fnx_api: FNXApi,
    prims_to_reset: Set[str], manual_min_bound=None, manual_max_bound=None,
):
    """
    Applies coloring based on a global property name (e.g., "Temperature").
    """
    if not log_field or not user_config:
        return None, None, None, None, set()

    stage = omni.usd.get_context().get_stage()
    if not stage:
        if log_field:
            log_field.model.set_value("Error: No USD stage is currently open.")
        return None, None, None, None, set()

    if prims_to_reset:
        _reset_prim_colors(stage, prims_to_reset)
    
    newly_colored_prims = set()

    selected_prop_index = property_combo.model.get_item_value_model().as_int
    selected_prop_name = property_names_for_viz[selected_prop_index]
    selected_cmap_index = colormap_combo.model.get_item_value_model().as_int
    selected_cmap = COLOR_MAP_OPTIONS[selected_cmap_index]
    
    log_text = f"Visualizing '{selected_prop_name}' with '{selected_cmap}' colormap.\n"
    log_text += "-------------------------------------\n"
    
    io_dir = user_config.Setup.IOFileDirectory
    mapping_json_path = os.path.join(io_dir, "FlownexMapping.json")
    
    # The mapping file is used as a fallback only.  The primary coloring path
    # scans the stage directly for prims tagged with ``flownex:componentName``,
    # so a missing mapping file is not fatal.
    if not os.path.exists(mapping_json_path):
        log_text += f"Note: Mapping file not found at {mapping_json_path}. Will rely on stage scan only.\n"
        comp_to_prim_map: Dict[str, List[str]] = {}
    else:
        try:
            comp_to_prim_map = _load_component_to_prim_map(mapping_json_path)
        except Exception as e:
            log_text += f"Warning: Could not load mapping file ({e}). Will rely on stage scan only.\n"
            comp_to_prim_map = {}

    if not fnx_outputs:
        log_field.model.set_value(log_text + "Error: No Flownex outputs loaded.")
        return None, None, None, None, newly_colored_prims

    # Match on any human-readable field so that user-defined Category / Description
    # values (e.g. Category="Temperature") drive the visualisation even when the
    # Flownex PropertyIdentifier is an internal API name that doesn't contain the
    # selected property word.
    def _output_matches(out: OutputDefinition, name: str) -> bool:
        n = name.lower()
        return (
            n in (out.PropertyIdentifier or "").lower()
            or n in (out.Category or "").lower()
            or n in (out.Description or "").lower()
            or n in (out.Key or "").lower()
        )

    outputs_to_visualize = [out for out in fnx_outputs if _output_matches(out, selected_prop_name)]
    
    if not outputs_to_visualize:
        log_text += f"No output properties found containing '{selected_prop_name}'.\n"
        log_text += f"Binding fallback material '{_FALLBACK_MATERIAL_PATH}' to all prims in the mapping file.\n"
        log_field.model.set_value(log_text)

        for paths in comp_to_prim_map.values():
            for path_str in _normalize_prim_paths(paths):
                prim = stage.GetPrimAtPath(path_str)
                if _apply_fallback_material_to_prim(stage, prim) > 0:
                    newly_colored_prims.add(path_str)

        return None, None, None, None, newly_colored_prims

    unit = outputs_to_visualize[0].Unit if outputs_to_visualize else ""
    full_label = f"{selected_prop_name} ({unit})" if unit else selected_prop_name

    vmin, vmax = None, None
    if manual_min_bound is not None and manual_max_bound is not None:
        vmin, vmax = manual_min_bound, manual_max_bound
        log_text += f"Using manual bounds: [{vmin:.3g}, {vmax:.3g}] {unit}\n"
    else:
        values = []
        for o in outputs_to_visualize:
            val_str = output_fields.get(o.Key)
            if val_str is None or val_str == "":
                continue
            try:
                values.append(float(val_str))
            except (ValueError, TypeError):
                pass
        vmin, vmax = (min(values), max(values)) if values else (0.0, 1.0)
        log_text += f"Using global auto-range: [{vmin:.3g}, {vmax:.3g}] {unit}\n"
    
    if abs(vmin - vmax) < 1e-9: vmax = vmin + 1.0

    property_ranges = {o.Key: {"min": vmin, "max": vmax} for o in outputs_to_visualize}
    
    processed, errors, skipped = 0, 0, 0
    # Track which ComponentIdentifiers actually received a colour so that the
    # fallback-material logic below can identify the remainder without relying
    # on prim-path set subtraction (which breaks when colored_paths contains
    # Mesh paths from the direct scan rather than the JSON-mapped parent paths).
    colored_component_ids: Set[str] = set()
    
    for out_def in outputs_to_visualize:
        value_str = output_fields.get(out_def.Key)
        if value_str is None:
            skipped += 1
            continue
        try: value = float(value_str)
        except (ValueError, TypeError):
            skipped += 1
            continue

        result_info = _visualize_single_component(
            output_def=out_def, value=value, comp_to_prim_map=comp_to_prim_map,
            property_ranges=property_ranges, cmap=selected_cmap,
        )
        
        if result_info["status"] == "ok":
            processed += result_info.get("colored_prims", 1)
            newly_colored_prims.update(result_info["colored_paths"])
            colored_component_ids.add(out_def.ComponentIdentifier)
        elif "Not found in stage scan or mapping file" in result_info["message"]:
            skipped += 1
        else:
            errors += 1

    # Apply fallback material to components that are in the mapping but have no
    # result for the selected property (or whose value was missing/invalid).
    # We track by ComponentIdentifier, not prim path, so the check is correct
    # whether colored_paths contains Mesh paths (direct scan) or mapping paths.
    fallback_count = 0
    for comp_id, paths in comp_to_prim_map.items():
        if comp_id in colored_component_ids:
            continue
        for path_str in _normalize_prim_paths(paths):
            prim = stage.GetPrimAtPath(path_str)
            if _apply_fallback_material_to_prim(stage, prim) > 0:
                newly_colored_prims.add(path_str)
                fallback_count += 1

    log_text += f"\nVisualization complete.\n"
    log_text += f"  - Colored {processed} prims (geometry and lights).\n"
    log_text += f"  - Skipped {skipped} (not in mapping or no valid data).\n"
    log_text += f"  - Encountered {errors} errors during coloring.\n"
    if fallback_count:
        log_text += f"  - Applied '{_FALLBACK_MATERIAL_PATH}' to {fallback_count} prims with no data for '{selected_prop_name}'.\n"
    log_field.model.set_value(log_text)

    return vmin, vmax, selected_cmap, full_label, newly_colored_prims

def generate_colorbar_image(
    vmin: float, vmax: float, cmap_name: str, label: str, width: int = 800, height: int = 50
) -> Optional[tuple]:
    """Generates a colorbar image using Matplotlib and returns raw bytes and dimensions."""
    if not MATPLOTLIB_AVAILABLE:
        print("[viz] Matplotlib not found, cannot generate colorbar.")
        return None

    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=300)
    fig.patch.set_alpha(0.0)
    ax.set_axis_off()
    
    cax = fig.add_axes([0.05, 0.4, 0.9, 0.4])

    try: cmap = plt.get_cmap(cmap_name)
    except ValueError:
        print(f"[viz] Warning: Colormap '{cmap_name}' not found. Falling back to 'viridis'.")
        cmap = plt.get_cmap("viridis")

    norm = Normalize(vmin=vmin, vmax=vmax)
    mappable = cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = plt.colorbar(mappable, cax=cax, orientation="horizontal")

    cb.set_label(label, color="white", fontsize=14, weight="bold")
    cb.ax.xaxis.set_major_locator(MaxNLocator(nbins=5, prune='both'))
    cb.ax.tick_params(colors="white", labelsize=12)
    cb.outline.set_edgecolor("white")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)

    if not PILLOW_AVAILABLE:
        print("[viz] Pillow not found, cannot guarantee correct image format.")
        return None

    try:
        buf.seek(0)
        with Image.open(buf) as pil_image:
            rgba_image = pil_image.convert("RGBA")
            return (bytearray(rgba_image.tobytes()), [rgba_image.width, rgba_image.height])
    except Exception as e:
        print(f"[viz] [ERROR] Failed to process image with Pillow: {e}")
        return None