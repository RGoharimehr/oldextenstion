import os
import csv
import json
from typing import Dict, Optional, Tuple, List, Set

from .fnx_api import FNXApi
from .fnx_io_definition import OutputDefinition
import omni.usd
from pxr import Usd, UsdGeom, Gf, Vt, Sdf, UsdLux


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

# --- NEW HELPER FUNCTION to avoid repeated code ---
def _apply_color_to_prim(prim: Usd.Prim, rgb: Tuple[float, float, float]) -> int:
    """Applies a color to a single prim, handling both lights and geometry. Returns count of items colored."""
    if not prim or not prim.IsValid():
        return 0

    colored_count = 0

    # prim.HasAPI() is the correct way to check whether an applied API schema is
    # present on a prim.  UsdLux.LightAPI(prim).__bool__() only checks prim.IsValid()
    # (inherited from UsdAPISchemaBase) and is therefore *always* True for any valid
    # prim – which would send every geometry prim through the light branch.
    if prim.HasAPI(UsdLux.LightAPI):
        try:
            light_api = UsdLux.LightAPI(prim)
            color_attr = light_api.CreateColorAttr()
            color_attr.Set(Gf.Vec3f(*rgb))
            colored_count += 1
        except Exception as e:
            print(f"[viz] Failed to set color on light {prim.GetPath()}: {e}")
    else:
        # If not a light, find and color all Gprims under it
        def find_and_color_gprims(p: Usd.Prim):
            nonlocal colored_count
            if UsdGeom.Gprim(p):
                try:
                    gprim = UsdGeom.Gprim(p)
                    color_attr = gprim.CreateDisplayColorAttr()
                    color_attr.Set([Gf.Vec3f(*rgb)])
                    colored_count += 1
                except Exception as e:
                    print(f"[viz] Failed to set displayColor on {p.GetPath()}: {e}")
            for child in p.GetChildren():
                find_and_color_gprims(child)
        find_and_color_gprims(prim)
    
    return colored_count


def _reset_prim_colors(stage: Usd.Stage, prim_paths: Set[str]):
    """Blocks color attributes on a set of prims to reset them."""
    if not stage or not prim_paths:
        return
    
    with Sdf.ChangeBlock():
        for path_str in prim_paths:
            prim = stage.GetPrimAtPath(path_str)
            if not prim or not prim.IsValid():
                continue

            if prim.HasAPI(UsdLux.LightAPI) and prim.HasAttribute("color"):
                try: prim.GetAttribute("color").Block()
                except Exception as e: print(f"[viz] Failed to block color on light {prim.GetPath()}: {e}")
            else:
                def find_and_block_gprim_color(p: Usd.Prim):
                    if p.HasAttribute("displayColor"):
                        try: p.GetAttribute("displayColor").Block()
                        except Exception as e: print(f"[viz] Failed to block displayColor on {p.GetPath()}: {e}")
                    for child in p.GetChildren():
                        find_and_block_gprim_color(child)
                find_and_block_gprim_color(prim)


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


def _visualize_single_component(
    output_def: OutputDefinition, value: float, comp_to_prim_map: Dict[str, List[str]], 
    property_ranges: Dict[str, Dict[str, float]], cmap: str, usd_context=None,
) -> Dict[str, object]:
    """Helper to visualize a single component, applying color to all its mapped prims."""
    key = output_def.Key
    component_id = output_def.ComponentIdentifier
    info = { "key": key, "status": "error", "message": "", "colored_prims": 0, "colored_paths": [] }

    prim_paths = comp_to_prim_map.get(component_id)
    if not prim_paths:
        info["message"] = "Not found in mapping file"
        return info

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
    for prim_path in prim_paths:
        prim = stage.GetPrimAtPath(prim_path)
        colored_count = _apply_color_to_prim(prim, rgb)
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
    if stage and prims_to_reset:
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
    
    if not os.path.exists(mapping_json_path):
        log_field.model.set_value(log_text + f"Error: Mapping file not found at {mapping_json_path}")
        return None, None, None, None, newly_colored_prims

    try:
        comp_to_prim_map = _load_component_to_prim_map(mapping_json_path)
    except Exception as e:
        log_field.model.set_value(log_text + f"Error loading mapping file: {e}")
        return None, None, None, None, newly_colored_prims

    if not fnx_outputs:
        log_field.model.set_value(log_text + "Error: No Flownex outputs loaded.")
        return None, None, None, None, newly_colored_prims

    outputs_to_visualize = [out for out in fnx_outputs if selected_prop_name.lower() in out.PropertyIdentifier.lower()]
    
    if not outputs_to_visualize:
        log_text += f"No output properties found containing '{selected_prop_name}'.\n"
        log_text += "Setting all mapped prims to silver as a placeholder."
        log_field.model.set_value(log_text)
        
        # --- FIX: Color all mapped prims silver ---
        silver_color = (0.75, 0.75, 0.75)
        all_mapped_paths = {path for paths in comp_to_prim_map.values() for path in paths}
        for path_str in all_mapped_paths:
            prim = stage.GetPrimAtPath(path_str)
            if _apply_color_to_prim(prim, silver_color) > 0:
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
        elif "Not found in mapping file" in result_info["message"]:
            skipped += 1
        else:
            errors += 1

    log_text += f"\nVisualization complete.\n"
    log_text += f"  - Colored {processed} prims (geometry and lights).\n"
    log_text += f"  - Skipped {skipped} (not in mapping or no valid data).\n"
    log_text += f"  - Encountered {errors} errors during coloring.\n"
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