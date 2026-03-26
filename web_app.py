"""
Flownex Web Interface
=====================
Flask REST-API server that runs **inside the Omniverse extension process**
and replaces the omni.ui window with a browser-based UI.

Usage (from extension.py)
--------------------------
    from . import web_app
    web_app.start_server(host="0.0.0.0", port=5000)
    web_app.stop_server()

The web app uses the same FNXApi / FlownexIO modules as the extension, so
no separate Flownex connection is made and the same config files are shared.

For operations that must run on the Omniverse main thread (USD mutations),
the extension sets ``_state._event_loop`` at startup so Flask handlers can
schedule work there via ``_run_on_omni(fn)``.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from flask import Flask, jsonify, request, send_from_directory

# ---------------------------------------------------------------------------
# Package imports (relative – runs inside Omniverse's Python interpreter)
# ---------------------------------------------------------------------------
from .fnx_api import FNXApi
from .fnx_io_definition import FlownexIO, InputDefinition, OutputDefinition
from .viz_utils import COLOR_MAP_OPTIONS, get_visualizable_properties

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_WEB_UI_DIR = Path(__file__).parent / "web_ui"
_MAX_HISTORY_SIZE = 300   # data-points retained per simulation run (≈5 min at 1 s interval)
_MAX_LOG_ENTRIES  = 200   # log lines retained; keeps the /api/simulation/status payload small


# ---------------------------------------------------------------------------
# Simulation state
# ---------------------------------------------------------------------------

class _SimState:
    """
    Mutable simulation state shared between Flask handlers and the background
    polling thread.

    Thread-safety
    -------------
    ``output_values``, ``history``, and ``log`` are mutated from both the
    Flask handler thread and the polling thread; all three writes are guarded
    by ``_lock``.
    """

    def __init__(self):
        self.api: FNXApi        = FNXApi()
        self.io:  FlownexIO     = FlownexIO()

        self.output_values: Dict[str, Any]       = {}
        self.history:       List[Dict[str, Any]] = []
        self._transient_running                  = False
        self._timer:        Optional[threading.Timer] = None
        self._lock                               = threading.Lock()
        self.log:           List[str]            = []

        # Visualization settings read by extension.py to colour USD prims.
        self.viz_settings: Dict[str, Any] = {
            "property_index": 0,
            "colormap_index": 0,
            "manual_min":     None,
            "manual_max":     None,
        }

        # Tracks the most-recently applied value for every input key so the
        # web UI can show current IT Load / Ambient Temp / etc. in the KPI bar.
        self.input_values: Dict[str, Any] = {}
        self._load_input_defaults()

        # Called after every output fetch; set by extension.py.
        # Signature: on_outputs_ready(output_values: dict, fnx_outputs: list)
        self.on_outputs_ready: Optional[Callable] = None

        # Omniverse asyncio event loop; set by extension.py so Flask handlers
        # can schedule USD-mutating operations on the main thread.
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Input default values helper
    # ------------------------------------------------------------------

    def _load_input_defaults(self) -> None:
        """Initialise ``input_values`` with the default value of every input definition.
        Existing user-set values are preserved (not overwritten)."""
        for kind in (self.io.LoadDynamicInputs(), self.io.LoadStaticInputs()):
            if kind:
                for inp in kind:
                    if inp.Key not in self.input_values:
                        self.input_values[inp.Key] = inp.DefaultValue

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        ts    = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        print(entry)
        with self._lock:
            self.log.append(entry)
            if len(self.log) > _MAX_LOG_ENTRIES:
                self.log = self.log[-_MAX_LOG_ENTRIES:]

    def get_log(self) -> List[str]:
        with self._lock:
            return list(self.log)

    # ------------------------------------------------------------------
    # Omniverse-thread runner
    # ------------------------------------------------------------------

    def run_on_omni(self, fn: Callable, timeout: float = 30.0) -> Any:
        """
        Schedule *fn* to run on the Omniverse main thread and block until it
        completes (or *timeout* seconds pass).  Returns the function's return
        value, or raises on error / timeout.

        Required for any USD-mutating operations (deinstance, mapping, viz).
        """
        if self._event_loop is None:
            raise RuntimeError(
                "Omniverse event loop not registered on web_app._state._event_loop. "
                "Ensure extension.py sets _state._event_loop before calling "
                "run_on_omni()."
            )

        fut: concurrent.futures.Future = concurrent.futures.Future()

        async def _wrapper():
            import omni.kit.app  # type: ignore
            await omni.kit.app.get_app().next_update_async()
            try:
                fut.set_result(fn())
            except Exception as exc:
                fut.set_exception(exc)

        self._event_loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(_wrapper())
        )
        return fut.result(timeout=timeout)

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def ensure_connected(self) -> str:
        project = self.io.Setup.FlownexProject
        if not project:
            return "No Flownex project configured."
        ok = self.api.LaunchFlownexIfNeeded(project)
        return "Connected." if ok else "Failed to connect to Flownex."

    # ------------------------------------------------------------------
    # Output fetching
    # ------------------------------------------------------------------

    def _fetch_outputs(self) -> List[OutputDefinition]:
        """Pull all output values from Flownex and update history."""
        fnx_outputs = self.io.LoadOutputs() or []
        point: Dict[str, Any] = {}

        for out in fnx_outputs:
            val: Optional[Any] = None
            if out.Unit:
                val = self.api.GetPropertyValueUnit(
                    out.ComponentIdentifier, out.PropertyIdentifier, out.Unit
                )
            else:
                raw = self.api.GetPropertyValue(
                    out.ComponentIdentifier, out.PropertyIdentifier
                )
                if raw is not None:
                    try:
                        val = float(raw)
                    except (ValueError, TypeError):
                        val = raw

            if val is not None:
                self.output_values[out.Key] = val
                point[out.Key] = val

        if point:
            interval = float(self.io.Setup.ResultPollingInterval)
            with self._lock:
                last_t = (
                    self.history[-1].get("Time", -interval)
                    if self.history
                    else -interval
                )
                point["Time"] = last_t + interval
                self.history.append(point)
                if len(self.history) > _MAX_HISTORY_SIZE:
                    self.history = self.history[-_MAX_HISTORY_SIZE:]

        return fnx_outputs

    def _notify_outputs_ready(self, fnx_outputs: list):
        if self.on_outputs_ready is not None:
            try:
                self.on_outputs_ready(dict(self.output_values), fnx_outputs)
            except Exception as exc:
                print(f"[web_app] on_outputs_ready callback error: {exc}")

    # ------------------------------------------------------------------
    # Transient simulation
    # ------------------------------------------------------------------

    def _transient_step(self):
        if not self._transient_running:
            return
        try:
            fnx_outputs = self._fetch_outputs()
            self._notify_outputs_ready(fnx_outputs)
        except Exception as exc:
            self._log(f"Polling error: {exc}")

        if self._transient_running:
            interval = float(self.io.Setup.ResultPollingInterval)
            self._timer = threading.Timer(interval, self._transient_step)
            self._timer.daemon = True
            self._timer.start()

    def start_transient(self) -> Dict[str, Any]:
        if self._transient_running:
            return {"ok": False, "message": "Transient simulation already running."}

        self.io = FlownexIO()
        msg = self.ensure_connected()
        if self.api.AttachedProject is None:
            return {"ok": False, "message": msg}

        fnx_outputs = self.io.LoadOutputs() or []
        if not fnx_outputs:
            return {"ok": False, "message": "No output definitions found in Outputs.csv."}

        if not self.api.StartTransientSimulation():
            return {"ok": False, "message": "Failed to start transient simulation."}

        self._transient_running = True
        self._transient_step()
        self._log("Transient simulation started.")
        return {"ok": True, "message": "Transient simulation started."}

    def stop_transient(self) -> Dict[str, Any]:
        self._transient_running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.api.StopTransientSimulation()
        self._log("Transient simulation stopped.")
        return {"ok": True, "message": "Transient simulation stopped."}

    # ------------------------------------------------------------------
    # Steady-state simulation
    # ------------------------------------------------------------------

    def run_steady_state(self, load_defaults: bool = False) -> Dict[str, Any]:
        self.io = FlownexIO()
        msg = self.ensure_connected()
        if self.api.AttachedProject is None:
            return {"ok": False, "message": msg}

        if load_defaults:
            self._apply_defaults()
            self._log("Input defaults applied.")

        self._log("Running steady-state simulation…")
        success = self.api.RunSteadyStateSimulationBlocking()
        if success:
            fnx_outputs = self._fetch_outputs()
            self._notify_outputs_ready(fnx_outputs)
            self._log("Steady-state simulation complete.")
            return {
                "ok":      True,
                "message": "Steady-state simulation complete.",
                "outputs": dict(self.output_values),
            }

        self._log("Steady-state simulation failed.")
        return {"ok": False, "message": "Steady-state simulation failed."}

    def _apply_defaults(self):
        all_inputs: List[InputDefinition] = []
        for kind in (self.io.LoadDynamicInputs(), self.io.LoadStaticInputs()):
            if kind:
                all_inputs.extend(kind)

        for inp in all_inputs:
            if inp.Unit:
                self.api.SetPropertyValueUnit(
                    inp.ComponentIdentifier,
                    inp.PropertyIdentifier,
                    float(inp.DefaultValue),
                    inp.Unit,
                )
            else:
                self.api.SetPropertyValue(
                    inp.ComponentIdentifier,
                    inp.PropertyIdentifier,
                    str(inp.DefaultValue),
                )
            self.input_values[inp.Key] = inp.DefaultValue

    # ------------------------------------------------------------------
    # Individual input update
    # ------------------------------------------------------------------

    def set_input_value(self, key: str, value: Any) -> Dict[str, Any]:
        all_inputs: List[InputDefinition] = []
        for kind in (self.io.LoadDynamicInputs(), self.io.LoadStaticInputs()):
            if kind:
                all_inputs.extend(kind)

        for inp in all_inputs:
            if inp.Key != key:
                continue
            msg = self.ensure_connected()
            if self.api.AttachedProject is None:
                return {"ok": False, "message": msg}

            if inp.Unit:
                self.api.SetPropertyValueUnit(
                    inp.ComponentIdentifier,
                    inp.PropertyIdentifier,
                    float(value),
                    inp.Unit,
                )
            else:
                self.api.SetPropertyValue(
                    inp.ComponentIdentifier,
                    inp.PropertyIdentifier,
                    str(value),
                )

            # Always track the new value so the KPI bar stays current
            self.input_values[key] = value
            if self.io.Setup.SolveOnChange:
                return self.run_steady_state(load_defaults=False)
            return {"ok": True, "message": f"Set {key} = {value}"}

        return {"ok": False, "message": f"Input key '{key}' not found."}

    @property
    def transient_running(self) -> bool:
        return self._transient_running


# Module-level singleton created once on import
_state = _SimState()


# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------

def _inputs_to_json(inputs) -> List[Dict[str, Any]]:
    if not inputs:
        return []
    return [
        {
            "key":                  i.Key,
            "description":          i.Description,
            "componentIdentifier":  i.ComponentIdentifier,
            "propertyIdentifier":   i.PropertyIdentifier,
            "editType":             i.EditType,
            "min":                  i.Min,
            "max":                  i.Max,
            "step":                 i.Step,
            "unit":                 i.Unit or "",
            "defaultValue":         i.DefaultValue,
        }
        for i in inputs
    ]


def _outputs_to_json(outputs) -> List[Dict[str, Any]]:
    if not outputs:
        return []
    return [
        {
            "category":            o.Category,
            "key":                 o.Key,
            "description":         o.Description,
            "componentIdentifier": o.ComponentIdentifier,
            "propertyIdentifier":  o.PropertyIdentifier,
            "unit":                o.Unit or "",
            "currentValue":        _state.output_values.get(o.Key),
        }
        for o in outputs
    ]


# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=str(_WEB_UI_DIR), static_url_path="/ui")


# -- frontend ---------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(str(_WEB_UI_DIR), "index.html")


# -- config -----------------------------------------------------------------

@app.route("/api/config", methods=["GET"])
def get_config():
    s = _state.io.Setup
    return jsonify({
        "FlownexProject":      s.FlownexProject,
        "IOFileDirectory":     s.IOFileDirectory,
        "SolveOnChange":       s.SolveOnChange,
        "ResultPollingInterval": s.ResultPollingInterval,
    })


@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.get_json(force=True) or {}
    s = _state.io.Setup
    if "FlownexProject"       in data: s.FlownexProject       = data["FlownexProject"]
    if "IOFileDirectory"      in data: s.IOFileDirectory      = data["IOFileDirectory"]
    if "SolveOnChange"        in data: s.SolveOnChange        = bool(data["SolveOnChange"])
    if "ResultPollingInterval" in data: s.ResultPollingInterval = str(data["ResultPollingInterval"])
    _state.io.Save()
    _state.io = FlownexIO()  # reload from disk
    _state._load_input_defaults()  # refresh KPI input values from new config
    return jsonify({"ok": True})


# -- inputs -----------------------------------------------------------------

@app.route("/api/inputs", methods=["GET"])
def get_dynamic_inputs():
    return jsonify(_inputs_to_json(_state.io.LoadDynamicInputs()))


@app.route("/api/static-inputs", methods=["GET"])
def get_static_inputs():
    return jsonify(_inputs_to_json(_state.io.LoadStaticInputs()))


@app.route("/api/inputs/values", methods=["POST"])
def set_input_values():
    """Body: { "values": { "<key>": <value>, … } }"""
    data = request.get_json(force=True) or {}
    results = {
        key: _state.set_input_value(key, value)
        for key, value in (data.get("values") or {}).items()
    }
    return jsonify({"ok": True, "results": results})


# -- outputs ----------------------------------------------------------------

@app.route("/api/outputs", methods=["GET"])
def get_outputs():
    return jsonify(_outputs_to_json(_state.io.LoadOutputs()))


# -- visualization settings -------------------------------------------------

@app.route("/api/viz/settings", methods=["GET"])
def get_viz_settings():
    return jsonify({
        "settings":       _state.viz_settings,
        "propertyOptions": get_visualizable_properties(),
        "colormapOptions": COLOR_MAP_OPTIONS,
    })


@app.route("/api/viz/settings", methods=["POST"])
def set_viz_settings():
    data = request.get_json(force=True) or {}
    for key in ("property_index", "colormap_index", "manual_min", "manual_max"):
        if key in data:
            _state.viz_settings[key] = data[key]
    return jsonify({"ok": True, "settings": _state.viz_settings})


# -- simulation control -----------------------------------------------------

@app.route("/api/simulation/status", methods=["GET"])
def sim_status():
    return jsonify({
        "transientRunning":  _state.transient_running,
        "flownexAvailable":  _state.api.IsFnxAvailable(),
        "connected":         _state.api.AttachedProject is not None,
        "outputs":           dict(_state.output_values),
        "inputValues":       dict(_state.input_values),
        "log":               _state.get_log()[-50:],
    })


@app.route("/api/simulation/start-transient", methods=["POST"])
def start_transient():
    return jsonify(_state.start_transient())


@app.route("/api/simulation/stop-transient", methods=["POST"])
def stop_transient():
    return jsonify(_state.stop_transient())


@app.route("/api/simulation/steady-state", methods=["POST"])
def run_steady_state():
    return jsonify(_state.run_steady_state(load_defaults=False))


@app.route("/api/simulation/load-defaults", methods=["POST"])
def load_defaults_and_solve():
    return jsonify(_state.run_steady_state(load_defaults=True))


@app.route("/api/history", methods=["GET"])
def get_history():
    with _state._lock:
        return jsonify(list(_state.history))


# -- results mapping (USD operations – run on Omniverse main thread) --------

@app.route("/api/mapping/add-attribute", methods=["POST"])
def mapping_add_attribute():
    """
    Add the ``flownex:componentName`` attribute to all prims under *root*.
    Body (optional): { "root": "/World" }
    """
    data = request.get_json(force=True) or {}
    root = data.get("root", "/World")

    from .flownex_attr_tools import deinstance_and_add_flownex

    try:
        result = _state.run_on_omni(lambda: deinstance_and_add_flownex(root))
        return jsonify({"ok": True, "message": result})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)})


@app.route("/api/mapping/generate", methods=["POST"])
def mapping_generate():
    """Generate FlownexMapping.json from the current stage + Outputs.csv."""
    from .flownex_attr_tools import map_outputs_to_prims

    io_dir = _state.io.Setup.IOFileDirectory
    try:
        result, _ = _state.run_on_omni(
            lambda: map_outputs_to_prims(io_dir, outputs_filename="Outputs.csv")
        )
        return jsonify({"ok": True, "message": result})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)})


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

_server_thread: Optional[threading.Thread] = None
_flask_server = None   # werkzeug WSGIServer; stored so stop_server() can shut it down


def start_server(host: str = "0.0.0.0", port: int = 5000):
    """
    Launch the Flask WSGI server using werkzeug's ``make_server`` so that
    ``stop_server()`` can call ``server.shutdown()`` and actually stop
    accepting connections when the extension is disabled.
    """
    global _server_thread, _flask_server
    if _server_thread and _server_thread.is_alive():
        print("[web_app] Server already running.")
        return

    try:
        from werkzeug.serving import make_server as _make_wsgi_server
        srv = _make_wsgi_server(host, port, app)
    except Exception as exc:
        print(f"[web_app] Failed to bind server on {host}:{port} – {exc}")
        return

    _flask_server = srv

    def _run():
        print(f"[web_app] Starting web server → http://{host}:{port}")
        srv.serve_forever()

    _server_thread = threading.Thread(target=_run, name="flownex-web", daemon=True)
    _server_thread.start()


def stop_server():
    """
    Stop the transient polling loop and shut down the HTTP server so that
    the web UI becomes unreachable immediately after the extension is disabled.
    """
    global _server_thread, _flask_server
    _state.stop_transient()
    _state.on_outputs_ready = None
    if _flask_server is not None:
        _flask_server.shutdown()
        _flask_server = None
    _server_thread = None
