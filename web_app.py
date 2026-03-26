#!/usr/bin/env python3
"""
Flownex Web Interface
=====================
Standalone Flask REST-API server that exposes Flownex simulation capabilities
via HTTP so that a browser (or any HTTP client) can control the simulation
without launching the Omniverse extension UI.

Usage
-----
  python web_app.py [--host 0.0.0.0] [--port 5000]

Then open http://localhost:5000 in any browser.

Architecture
------------
* Reads the same FlownexUser.json / Inputs.csv / Outputs.csv files that the
  Omniverse extension uses, so configuration written in one tool is immediately
  visible in the other.
* Wraps the Flownex COM API via pythonnet/clr.  If pythonnet is not installed,
  or Flownex is not installed on the machine, the server starts in "offline"
  mode: configuration and file management still work, but simulation calls
  return a clear error message.
* Transient simulation runs in a background thread; the /api/simulation/status
  endpoint lets the browser poll for the latest outputs and history.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Flask – required
# ---------------------------------------------------------------------------
try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError:
    print(
        "[web_app] Flask is not installed.\n"
        "Install it with:  pip install flask\n"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_SETTINGS_FILE = _HERE / "FlownexUser.json"
_WEB_UI_DIR = _HERE / "web_ui"

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
_DEFAULT_MAX_INPUT_VALUE = 10_000_000  # default upper bound for slider inputs
_MAX_HISTORY_SIZE = 300                # max simulation data-points retained
_MAX_LOG_ENTRIES = 200                 # max log lines retained in memory

# ---------------------------------------------------------------------------
# Flownex COM API (Windows-only, requires pythonnet + Flownex installation)
# ---------------------------------------------------------------------------
_CLR_AVAILABLE = False
try:
    import clr  # type: ignore  # pythonnet
    import Microsoft.Win32  # type: ignore
    _CLR_AVAILABLE = True
except ImportError:
    pass


def _get_flownex_directory() -> Optional[str]:
    """Return the Flownex install directory from the Windows registry."""
    if not _CLR_AVAILABLE:
        return None
    try:
        classes_root = Microsoft.Win32.RegistryKey.OpenBaseKey(
            Microsoft.Win32.RegistryHive.ClassesRoot,
            Microsoft.Win32.RegistryView.Default,
        )
        clsid_root = classes_root.OpenSubKey("CLSID")
        fnx_key = clsid_root.OpenSubKey("{FD40D175-FED4-4619-8571-36336DD2B8E1}")
        if fnx_key is not None:
            local_server = fnx_key.OpenSubKey("LocalServer32")
            value = str(local_server.GetValue(None))
            value = value.replace(" /automation", "")
            return value.rpartition("FlownexSE.exe")[0]
    except Exception as exc:
        print(f"[web_app] Registry lookup failed: {exc}")
    return None


# ---------------------------------------------------------------------------
# Lightweight config helpers (no omni dependencies)
# ---------------------------------------------------------------------------

def _read_config() -> Dict[str, Any]:
    """Return the content of FlownexUser.json as a dict."""
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[web_app] Cannot read settings: {exc}")
    return {
        "FlownexProject": "",
        "IOFileDirectory": "",
        "SolveOnChange": False,
        "ResultPollingInterval": "1.0",
    }


def _write_config(cfg: Dict[str, Any]):
    """Persist *cfg* to FlownexUser.json."""
    _SETTINGS_FILE.write_text(
        json.dumps(cfg, indent=2), encoding="utf-8"
    )


def _load_inputs(kind: str = "dynamic") -> List[Dict[str, Any]]:
    """
    Load input definitions from Inputs.csv (dynamic) or StaticInputs.csv.
    Returns a list of plain dicts for easy JSON serialisation.
    """
    cfg = _read_config()
    io_dir = cfg.get("IOFileDirectory", "")
    filename = "StaticInputs.csv" if kind == "static" else "Inputs.csv"
    csv_path = os.path.join(io_dir, filename)
    if not os.path.isfile(csv_path):
        return []
    rows = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                edit_type = row.get("EditType", "slider")
                default_raw = row.get("DefaultValue", "0")
                if edit_type == "checkbox":
                    default = str(default_raw).lower() in ("true", "1", "yes", "y")
                else:
                    default = float(default_raw) if default_raw else 0.0
                rows.append(
                    {
                        "key": row.get("Key", ""),
                        "description": row.get("Description", ""),
                        "componentIdentifier": row.get("ComponentIdentifier", ""),
                        "propertyIdentifier": row.get("PropertyIdentifier", ""),
                        "editType": edit_type,
                        "min": float(row.get("Min") or 0),
                        "max": float(row.get("Max") or 10_000_000),
                        "step": float(row.get("Step") or 1),
                        "unit": row.get("Unit", ""),
                        "defaultValue": default,
                    }
                )
            except Exception:
                pass
    return rows


def _load_outputs() -> List[Dict[str, Any]]:
    """Load output definitions from Outputs.csv."""
    cfg = _read_config()
    io_dir = cfg.get("IOFileDirectory", "")
    csv_path = os.path.join(io_dir, "Outputs.csv")
    if not os.path.isfile(csv_path):
        return []
    rows = []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(
                {
                    "category": (row.get("Category") or "").strip(),
                    "key": (row.get("Key") or "").strip(),
                    "description": (row.get("Description") or "").strip(),
                    "componentIdentifier": (row.get("ComponentIdentifier") or "").strip(),
                    "propertyIdentifier": (row.get("PropertyIdentifier") or "").strip(),
                    "unit": (row.get("Unit") or "").strip(),
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Flownex API wrapper
# ---------------------------------------------------------------------------

class _FlownexAPI:
    """
    Thin wrapper around the Flownex COM API.
    All methods return graceful errors when the API is unavailable.
    """

    def __init__(self):
        self._project = None
        self._flownex_se = None
        self._sim_controller = None
        self._net_builder = None
        self._prop_cache: Dict[str, Any] = {}
        self._available = False

        fnx_dir = _get_flownex_directory()
        if fnx_dir:
            try:
                clr.AddReference(fnx_dir + "IPS.Core.dll")
                import IPS  # type: ignore  # noqa: F401
                self._available = True
            except Exception as exc:
                print(f"[web_app] Cannot load Flownex IPS.Core.dll: {exc}")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def connected(self) -> bool:
        return self._project is not None

    def attach(self, project_path: str) -> str:
        if not self._available:
            return "Flownex API not available (pythonnet / installation missing)."
        if not os.path.isfile(project_path):
            return f"Project file not found: {project_path}"

        if self._project is not None and getattr(self, "_project_path", None) == project_path:
            return "Already connected."

        self.detach()
        try:
            import IPS  # type: ignore
            fnx_dir = _get_flownex_directory()
            IPS.Core.FlownexSEDotNet.InitialiseAssemblyResolver(fnx_dir)
            root_path = project_path[: -len(".proj")] + "_project\\"
            running = IPS.Core.FlownexSEDotNet.GetRunningFlownexInstances()
            if running:
                for inst in running:
                    if inst.Project is not None and os.path.normpath(
                        inst.Project.ProjectRootPath
                    ) == os.path.normpath(root_path):
                        self._project = inst.Project
                        self._flownex_se = inst
                        break
            if self._project is None:
                self._flownex_se = IPS.Core.FlownexSEDotNet.LaunchFlownexSE()
                self._flownex_se.OpenProject(project_path, "", "")
                self._project = self._flownex_se.Project

            if self._project is None:
                return f"Failed to open project: {project_path}"

            self._sim_controller = IPS.Core.SimulationControlHelper(
                self._project.SimulationControlHelper
            )
            self._net_builder = IPS.Core.NetworkBuilder(self._project.Builder)
            self._project_path = project_path
            return "Connected."
        except Exception as exc:
            return f"Error attaching to project: {exc}"

    def detach(self):
        try:
            if self._flownex_se is not None:
                self._flownex_se.CloseProject()
        except Exception:
            pass
        self._project = None
        self._flownex_se = None
        self._sim_controller = None
        self._net_builder = None
        self._prop_cache.clear()

    def _get_property(self, component: str, prop: str):
        key = f"{component}.{prop}"
        if key in self._prop_cache:
            return self._prop_cache[key]
        import IPS  # type: ignore
        el = IPS.Core.Element(self._project.GetElement(component))
        if el is None:
            return None
        p = IPS.Core.Property(el.GetPropertyFromFullDisplayName(prop))
        if p is None:
            return None
        self._prop_cache[key] = p
        return p

    def set_value(self, component: str, prop: str, value: str, unit: str = "") -> bool:
        if not self.connected:
            return False
        try:
            p = self._get_property(component, prop)
            if p is None:
                return False
            text = f"{value} {unit}".strip() if unit else str(value)
            p.SetValueFromString(text)
            return True
        except Exception as exc:
            print(f"[web_app] set_value error: {exc}")
            return False

    def get_value(self, component: str, prop: str, unit: str = "") -> Optional[float]:
        if not self.connected:
            return None
        try:
            from .fnx_units import UnitGroup  # relative within package if possible
        except ImportError:
            # Standalone: we'll do a simple numeric parse without unit conversion
            UnitGroup = None

        try:
            p = self._get_property(component, prop)
            if p is None:
                return None
            raw = p.GetValueAsString()
            if raw is None:
                return None
            parts = raw.split()
            numeric = float(parts[0])

            if unit and UnitGroup and len(parts) >= 3:
                ug = UnitGroup.GetUnitGroupFromIdentifierName(parts[1])
                if ug:
                    api_unit = ug.UnitFromName(" ".join(parts[2:]))
                    user_unit = ug.UnitFromName(unit)
                    if api_unit and user_unit:
                        numeric = UnitGroup.Convert(numeric, api_unit, user_unit)
            return numeric
        except Exception as exc:
            print(f"[web_app] get_value error: {exc}")
            return None

    def run_steady_state(self, timeout_ms: int = 120_000) -> bool:
        if not self.connected:
            return False
        try:
            return bool(
                self._sim_controller.SolveSteadyStateAndWaitToComplete(timeout_ms)
            )
        except Exception as exc:
            print(f"[web_app] run_steady_state error: {exc}")
            return False

    def start_transient(self) -> bool:
        if not self.connected:
            return False
        try:
            self._project.ResetTime()
            self._project.RunSimulation()
            return True
        except Exception as exc:
            print(f"[web_app] start_transient error: {exc}")
            return False

    def stop_transient(self) -> bool:
        if not self.connected:
            return False
        try:
            self._project.DeactivateSimulation()
            return True
        except Exception as exc:
            print(f"[web_app] stop_transient error: {exc}")
            return False


# ---------------------------------------------------------------------------
# Server-side simulation state
# ---------------------------------------------------------------------------

class _SimState:
    """Holds mutable simulation state shared between Flask handlers and the
    background polling thread."""

    def __init__(self):
        self.api = _FlownexAPI()
        self.output_values: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self._transient_running = False
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self.log: List[str] = []

    # -- helpers --

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        print(entry)
        with self._lock:
            self.log.append(entry)
            if len(self.log) > 200:
                self.log = self.log[-200:]

    def get_log(self) -> List[str]:
        with self._lock:
            return list(self.log)

    # -- output fetching --

    def fetch_outputs(self):
        outputs = _load_outputs()
        point: Dict[str, Any] = {}
        for out in outputs:
            val = self.api.get_value(
                out["componentIdentifier"],
                out["propertyIdentifier"],
                out["unit"],
            )
            if val is not None:
                self.output_values[out["key"]] = val
                point[out["key"]] = val

        if point:
            cfg = _read_config()
            interval = float(cfg.get("ResultPollingInterval", 1.0))
            last_t = (
                self.history[-1].get("Time", -interval)
                if self.history
                else -interval
            )
            point["Time"] = last_t + interval
            with self._lock:
                self.history.append(point)
                if len(self.history) > 300:
                    self.history = self.history[-300:]

    # -- transient loop --

    def _transient_step(self):
        if not self._transient_running:
            return
        try:
            self.fetch_outputs()
        except Exception as exc:
            self._log(f"Polling error: {exc}")

        cfg = _read_config()
        interval = float(cfg.get("ResultPollingInterval", 1.0))
        if self._transient_running:
            self._timer = threading.Timer(interval, self._transient_step)
            self._timer.daemon = True
            self._timer.start()

    def ensure_connected(self) -> str:
        cfg = _read_config()
        project = cfg.get("FlownexProject", "")
        if not project:
            return "No Flownex project configured."
        return self.api.attach(project)

    def start_transient(self) -> Dict[str, Any]:
        if self._transient_running:
            return {"ok": False, "message": "Transient simulation already running."}

        msg = self.ensure_connected()
        if not self.api.connected:
            return {"ok": False, "message": msg}

        # Apply current input defaults before starting
        self._apply_defaults()

        if not self.api.start_transient():
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
        self.api.stop_transient()
        self._log("Transient simulation stopped.")
        return {"ok": True, "message": "Transient simulation stopped."}

    def run_steady_state(self, load_defaults: bool = False) -> Dict[str, Any]:
        msg = self.ensure_connected()
        if not self.api.connected:
            return {"ok": False, "message": msg}

        if load_defaults:
            self._apply_defaults()
            self._log("Loaded defaults.")

        self._log("Running steady-state simulation…")
        success = self.api.run_steady_state()
        if success:
            self.fetch_outputs()
            self._log("Steady-state complete.")
            return {"ok": True, "message": "Steady-state simulation complete.", "outputs": dict(self.output_values)}
        else:
            self._log("Steady-state simulation failed.")
            return {"ok": False, "message": "Steady-state simulation failed."}

    def _apply_defaults(self):
        """Push all default values from Inputs.csv and StaticInputs.csv into Flownex."""
        for kind in ("dynamic", "static"):
            for inp in _load_inputs(kind):
                val = inp["defaultValue"]
                self.api.set_value(
                    inp["componentIdentifier"],
                    inp["propertyIdentifier"],
                    str(val),
                    inp["unit"],
                )

    def set_input_value(self, key: str, value: Any) -> Dict[str, Any]:
        """Set a single input by key and push to Flownex."""
        for kind in ("dynamic", "static"):
            for inp in _load_inputs(kind):
                if inp["key"] == key:
                    msg = self.ensure_connected()
                    if not self.api.connected:
                        return {"ok": False, "message": msg}
                    ok = self.api.set_value(
                        inp["componentIdentifier"],
                        inp["propertyIdentifier"],
                        str(value),
                        inp["unit"],
                    )
                    if ok:
                        cfg = _read_config()
                        if cfg.get("SolveOnChange"):
                            return self.run_steady_state()
                        return {"ok": True, "message": f"Set {key} = {value}"}
                    return {"ok": False, "message": f"Failed to set {key}."}
        return {"ok": False, "message": f"Input key '{key}' not found."}

    @property
    def transient_running(self) -> bool:
        return self._transient_running


# Module-level singleton
_state = _SimState()

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=str(_WEB_UI_DIR), static_url_path="/ui")


# -- frontend --

@app.route("/")
def index():
    return send_from_directory(str(_WEB_UI_DIR), "index.html")


# -- config --

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(_read_config())


@app.route("/api/config", methods=["POST"])
def set_config():
    cfg = _read_config()
    data = request.get_json(force=True) or {}
    for key in ("FlownexProject", "IOFileDirectory", "SolveOnChange", "ResultPollingInterval"):
        if key in data:
            cfg[key] = data[key]
    _write_config(cfg)
    return jsonify({"ok": True, "config": cfg})


# -- inputs --

@app.route("/api/inputs", methods=["GET"])
def get_dynamic_inputs():
    return jsonify(_load_inputs("dynamic"))


@app.route("/api/static-inputs", methods=["GET"])
def get_static_inputs():
    return jsonify(_load_inputs("static"))


@app.route("/api/inputs/values", methods=["POST"])
def set_input_values():
    """
    Body: { "values": { "<key>": <value>, ... } }
    """
    data = request.get_json(force=True) or {}
    results = {}
    for key, value in (data.get("values") or {}).items():
        results[key] = _state.set_input_value(key, value)
    return jsonify({"ok": True, "results": results})


# -- outputs --

@app.route("/api/outputs", methods=["GET"])
def get_outputs():
    defs = _load_outputs()
    merged = []
    for out in defs:
        merged.append(
            {**out, "currentValue": _state.output_values.get(out["key"])}
        )
    return jsonify(merged)


# -- simulation --

@app.route("/api/simulation/status", methods=["GET"])
def sim_status():
    return jsonify(
        {
            "transientRunning": _state.transient_running,
            "flownexAvailable": _state.api.available,
            "connected": _state.api.connected,
            "outputs": dict(_state.output_values),
            "log": _state.get_log()[-50:],
        }
    )


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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Flownex Web Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Bind port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    print("=" * 60)
    print("  Flownex Web Interface")
    print(f"  URL : http://{args.host}:{args.port}")
    print(f"  Flownex API available : {_state.api.available}")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    main()
