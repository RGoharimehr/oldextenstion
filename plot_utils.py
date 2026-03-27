import matplotlib.pyplot as plt
import io
from PIL import Image
from typing import List, Dict, Optional, Tuple

# --- Modern, high-contrast colors for plot lines ---
PLOT_COLORS = [
    '#00E6D9',  # Bright Cyan
    '#FF007F',  # Vivid Magenta
    '#9D6CFF',  # Bright Purple
    '#FFD700',  # Gold
    '#32CD32',  # Lime Green
    '#FF5733',  # Orange-Red
]

# --- Dark theme colors ---
FIG_BG_COLOR = '#23283D'  # Dark Navy Blue
AXES_BG_COLOR = '#23283D'
GRID_COLOR = '#444B6A'
TEXT_COLOR = '#EAEAEA'

def generate_plot_image_from_history(
    simulation_history: List[Dict],
    x_axis_key: str,
    y_axis_keys: List[str],
    key_to_label_map: Dict[str, str],
    plot_title: str = "Simulation Results",
    width: int = 800,
    height: int = 600
) -> Optional[Tuple[bytes, Tuple[int, int]]]:
    """
    Generates a dark-themed, styled plot using Matplotlib and returns it as an image.
    """
    if not simulation_history or not x_axis_key or not y_axis_keys:
        return None

    # --- Create the plot figure and axes ---
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    
    x_data = [d.get(x_axis_key) for d in simulation_history if d.get(x_axis_key) is not None]

    # --- Plot each selected Y-axis variable ---
    for i, y_key in enumerate(y_axis_keys):
        y_data = [d.get(y_key) for d in simulation_history if d.get(x_axis_key) is not None]
        color = PLOT_COLORS[i % len(PLOT_COLORS)]
        label = key_to_label_map.get(y_key, y_key)
        ax.plot(x_data, y_data, linestyle='-', linewidth=2.0, label=label, color=color)

    # --- Apply modern dark theme styling ---
    fig.patch.set_facecolor(FIG_BG_COLOR)
    ax.set_facecolor(AXES_BG_COLOR)

    ax.set_title(plot_title, color=TEXT_COLOR, fontsize=16, weight='bold')
    ax.set_xlabel(key_to_label_map.get(x_axis_key, x_axis_key), color=TEXT_COLOR, fontsize=12)
    ax.set_ylabel("Values", color=TEXT_COLOR, fontsize=12)

    ax.grid(True, which='both', linestyle='--', linewidth=0.5, color=GRID_COLOR)
    ax.tick_params(axis='x', colors=TEXT_COLOR)
    ax.tick_params(axis='y', colors=TEXT_COLOR)
    
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)

    # --- Convert plot to an image for the UI ---
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", bbox_inches='tight', pad_inches=0.1, facecolor=fig.get_facecolor())
        plt.close(fig) # Important to free memory
        buf.seek(0)
        with Image.open(buf) as pil_image:
            rgba_image = pil_image.convert("RGBA")
            return (bytearray(rgba_image.tobytes()), (rgba_image.width, rgba_image.height))
    except Exception as e:
        print(f"[Plotting] [ERROR] Failed to save or convert plot image: {e}")
        plt.close(fig)
        return None