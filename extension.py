"""
Flownex Omniverse Extension – Web UI mode
==========================================
The full omni.ui tab-based window is replaced by a browser-based interface
served by a Flask HTTP server embedded in the Omniverse process.

When this extension starts:
  1. A Flask server is launched in a daemon thread (default: port 5000).
  2. A minimal Omniverse window shows the browser URL.
  3. USD prim visualisation is driven by the web app's viz settings, updated
     after every simulation output fetch.

All simulation control (inputs, outputs, start/stop, steady-state, viz
settings, mapping) is done through the browser at http://localhost:5000.
"""

import asyncio
import omni.ext
import omni.kit.app
import omni.usd
import omni.ui as ui
from omni.ui import color as cl

from . import web_app
from .viz_utils import (
    COLOR_MAP_OPTIONS,
    get_visualizable_properties,
    visualize_property_layer,
    _reset_prim_colors,
)

_DEFAULT_HOST = "0.0.0.0"   # bind on all interfaces so phones/tablets on the LAN can connect
_DEFAULT_PORT = 5000


# ---------------------------------------------------------------------------
# Proxy: captures viz log messages instead of writing to omni.ui widgets
# ---------------------------------------------------------------------------

class _LogProxy:
    """Drop-in replacement for omni.ui.StringField used by visualize_property_layer."""

    def __init__(self):
        self._text = ""
        self.model = self  # self IS the model

    def set_value(self, text: str):
        self._text = text

    def get_value_as_string(self) -> str:
        return self._text


# ---------------------------------------------------------------------------
# Combo-box proxy: mirrors the omni.ui.ComboBox API expected by viz_utils
# ---------------------------------------------------------------------------

class _ComboProxy:
    """Wraps an integer index to look like an omni.ui.ComboBox to viz_utils."""

    def __init__(self, index: int):
        self.model = _ComboModel(index)


class _ComboModel:
    def __init__(self, index: int):
        self._index = index

    def get_item_value_model(self):
        return self

    @property
    def as_int(self) -> int:
        return self._index


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

class SimReadyPhysicsExtension(omni.ext.IExt):
    """Flownex Omniverse integration extension – web UI mode."""

    def on_startup(self, ext_id: str):
        self._ext_id          = ext_id
        self._last_colored_prims: set = set()
        self._usd_context     = omni.usd.get_context()
        self._window          = None

        # Capture the Omniverse asyncio event loop so Flask handlers can
        # schedule USD-mutating operations on the main thread.
        try:
            self._event_loop = asyncio.get_event_loop()
        except RuntimeError:
            self._event_loop = None

        # Share the event loop with the web app state.
        web_app._state._event_loop = self._event_loop

        # Register callback: invoked from the web app's polling thread after
        # every simulation output fetch.
        web_app._state.on_outputs_ready = self._on_outputs_ready

        # Mark the extension as alive so Flask endpoints accept requests.
        web_app._state.extension_alive = True

        # Launch the Flask server in a background daemon thread.
        web_app.start_server(_DEFAULT_HOST, _DEFAULT_PORT)

        # Minimal Omniverse window – shows the browser URL.
        # The server binds on 0.0.0.0 so any device on the same LAN can connect;
        # localhost:5000 works for the machine running Omniverse.
        local_url = f"http://localhost:{_DEFAULT_PORT}"
        self._window = ui.Window("Flownex Web Interface", width=480, height=100)
        with self._window.frame:
            with ui.VStack(spacing=4, style={"padding": 8}):
                ui.Label(
                    f"Web UI:  {local_url}",
                    style={"font_size": 18, "color": cl("#90caf9")},
                )
                ui.Label(
                    "Open the address above in any browser to control the simulation.",
                    style={"font_size": 13, "color": cl("#aaaaaa")},
                )
                ui.Label(
                    "LAN access: replace 'localhost' with this machine's IP address.",
                    style={"font_size": 12, "color": cl("#777777")},
                )

    # ------------------------------------------------------------------
    # Output-ready callback (invoked from web app background thread)
    # ------------------------------------------------------------------

    def _on_outputs_ready(self, output_fields: dict, fnx_outputs: list):
        """Schedule a USD visualization update on the Omniverse main thread."""
        if self._event_loop is None:
            return
        self._event_loop.call_soon_threadsafe(
            lambda of=output_fields, fo=fnx_outputs:
                asyncio.ensure_future(self._apply_viz_async(of, fo))
        )

    async def _apply_viz_async(self, output_fields: dict, fnx_outputs: list):
        """Wait for the next Omniverse frame, then apply USD prim colours."""
        await omni.kit.app.get_app().next_update_async()
        self._apply_viz(output_fields, fnx_outputs)

    def _apply_viz(self, output_fields: dict, fnx_outputs: list):
        """Apply USD prim coloring using the current viz settings from the web app."""
        stage = self._usd_context.get_stage()
        if not stage:
            return

        viz      = web_app._state.viz_settings
        props    = get_visualizable_properties()
        prop_idx = max(0, min(viz.get("property_index", 0), len(props) - 1))
        cmap_idx = max(0, min(viz.get("colormap_index", 0), len(COLOR_MAP_OPTIONS) - 1))

        log_proxy = _LogProxy()

        _, _, _, _, newly_colored = visualize_property_layer(
            log_field              = log_proxy,
            property_combo         = _ComboProxy(prop_idx),
            colormap_combo         = _ComboProxy(cmap_idx),
            property_names_for_viz = props,
            user_config            = web_app._state.io,
            fnx_outputs            = fnx_outputs,
            output_fields          = output_fields,
            fnx_api                = web_app._state.api,
            prims_to_reset         = self._last_colored_prims,
            manual_min_bound       = viz.get("manual_min"),
            manual_max_bound       = viz.get("manual_max"),
        )
        self._last_colored_prims = newly_colored

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def on_shutdown(self):
        # Mark the extension as inactive before stopping the server so that
        # any in-flight or queued Flask requests fail cleanly with 503 instead
        # of executing against half-torn-down state.
        web_app._state.extension_alive = False
        web_app._state.on_outputs_ready = None
        web_app._state._event_loop = None

        web_app.stop_server()

        if self._last_colored_prims:
            stage = self._usd_context.get_stage()
            if stage:
                _reset_prim_colors(stage, self._last_colored_prims)

        if self._window:
            self._window.destroy()
            self._window = None
