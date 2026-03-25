import omni.kit.commands
import omni.kit.app
import omni.ext
import omni.ui as ui
import omni.usd
from omni.ui import color as cl
from pxr import Usd
import os
import json

from .FlownexMain import FlownexMain
from .flownex_attr_tools import (
    deinstance_and_add_flownex,
    map_outputs_to_prims,
    export_project_to_zip,
    import_project_from_zip,
)
from .viz_utils import (
    COLOR_MAP_OPTIONS,
    visualize_property_layer,
    get_visualizable_properties,
    generate_colorbar_image,
)

try:
    import matplotlib
    matplotlib.use("Agg")
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False


class SimReadyPhysicsExtension(omni.ext.IExt):
    """Flownex Omniverse integration extension."""

    def on_startup(self, ext_id: str):
        self._is_ready = False

        self._ext_id = ext_id
        self._window = None
        self._WindowText = "Flownex Omniverse Integration"

        self._viz_update_counter = 0
        self._plot_update_counter = 0

        self._tabs = {}
        self._tab_buttons = {}
        self._current_tab = "Operating Conditions"

        self._FlownexMain = FlownexMain(ext_id=self._ext_id)
        self._FlownexMain.ui_extension = self

        self._usd_context = omni.usd.get_context()
        self._last_colored_prims = set()

        self._plot_window = None
        self._plot_requests = []
        self._y_axis_checkboxes = {}
        self._plot_key_to_label_map = {}
        self._plot_x_axis_key = "Time"

        self._property_bounds = {}
        self._current_viz_property = None

        self._plotting_tab_built = False
        self._plotting_tab_last_y_keys = frozenset()

        self._window = ui.Window(self._WindowText, width=500, height=600)
        with self._window.frame:
            self._build_window()

        self._is_ready = True

    def _update_ui_and_visualization(self):
        """Called by FlownexMain every time new data is fetched from Flownex.

        This is the single entry-point that keeps the visualization live:
          1. _apply_coloring_for_all_keys() – re-colors USD prims using the
             freshly fetched output values from _FlownexMain._outputFields.
          2. _update_plot_window_data()     – pushes new XY points into
             existing plot widgets (data-only, no widget reconstruction).
        """
        if not self._is_ready:
            return

        # Re-color USD prims with the latest Flownex output values.
        self._apply_coloring_for_all_keys()

        # Push new data into open plot widgets without rebuilding the UI.
        if self._plot_window and self._plot_window.visible:
            self._update_plot_window_data()

    def _build_window(self):
        with ui.VStack():
            with ui.HStack(
                height=150,
                width=ui.Percent(100),
                alignment=ui.Alignment.CENTER,
                spacing=0,
                style={"margin": 0, "padding": 0},
            ):
                ext_root = omni.kit.app.get_app().get_extension_manager().get_extension_path(self._ext_id)
                image_path = os.path.join(ext_root, "_data", "bottom logos.bmp")
                ui.Image(
                    image_path,
                    fill_policy=ui.FillPolicy.PRESERVE_ASPECT_FIT,
                    width=ui.Percent(100),
                    height=ui.Percent(100),
                    alignment=ui.Alignment.CENTER,
                )

            with ui.ScrollingFrame(
                height=60,
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                style={"margin": 5},
            ):
                with ui.HStack(spacing=7):
                    tab_definitions = {
                        "Operating Conditions": "[Operating Conditions]",
                        "Geometrical Design": "[Geometrical Design]",
                        "Results Visualization": "[Results Visualization]",
                        "plotting": "[Plotting]",
                        "configuration": "[Configuration]",
                        "Results Mapping": "[Results Mapping]",
                    }
                    for name, label in tab_definitions.items():
                        self._tab_buttons[name] = ui.Button(
                            label,
                            width=150,
                            clicked_fn=lambda n=name: self._show_tab(n),
                            style={"font_size": 16},
                        )

            self._tab_label = ui.Label("", height=20, style={"font_size": 16})
            ui.Separator(height=2)

            with ui.ZStack():
                self._tabs["Operating Conditions"] = ui.VStack()
                with self._tabs["Operating Conditions"]:
                    self._FlownexMain._build_Inputs_tab("dynamic")

                self._tabs["Geometrical Design"] = ui.VStack()
                with self._tabs["Geometrical Design"]:
                    self._FlownexMain._build_Inputs_tab("static")

                self._tabs["Results Visualization"] = ui.VStack()
                with self._tabs["Results Visualization"]:
                    self._build_results_viz_tab()

                self._tabs["plotting"] = ui.VStack(spacing=8, style={"padding": "8px"})

                self._tabs["configuration"] = ui.VStack()
                with self._tabs["configuration"]:
                    self._FlownexMain._build_config_tab()

                self._tabs["Results Mapping"] = ui.VStack()
                with self._tabs["Results Mapping"]:
                    self._build_results_mapping_tab()

            self._show_tab(self._current_tab)
            ui.Separator(height=5)

    def _show_tab(self, tab_name: str):
        self._current_tab = tab_name

        if tab_name == "plotting":
            # Only rebuild the plotting tab when the available variables have changed
            # or when the tab has never been built, not on every tab switch.
            current_y_keys = frozenset(
                k for k in self._get_plot_variable_options() if k != self._plot_x_axis_key
            )
            if not self._plotting_tab_built or current_y_keys != self._plotting_tab_last_y_keys:
                self._rebuild_plotting_tab()

        style_selected = {"Button": {"background_color": cl("#0050E0"), "font_size": 16}}
        style_unselected = {"Button": {"background_color": cl(0.2), "font_size": 16}}

        for name, button in self._tab_buttons.items():
            button.set_style(style_selected if name == tab_name else style_unselected)

        for name, frame in self._tabs.items():
            frame.visible = (name == tab_name)

    def on_shutdown(self):
        print("--- RUNNING on_shutdown ---")
        try:
            if self._plot_window:
                self._plot_window.destroy()

            if self._last_colored_prims and self._usd_context.get_stage():
                from .viz_utils import _reset_prim_colors
                _reset_prim_colors(self._usd_context.get_stage(), self._last_colored_prims)

            if self._FlownexMain:
                self._FlownexMain.ui_extension = None
                self._FlownexMain._cleanup()

            if self._window:
                self._window.destroy()

            self._tabs.clear()
        except Exception as e:
            print(f"--- ERROR inside on_shutdown: {e} ---")
        print("--- FINISHED on_shutdown ---")

    def _build_results_mapping_tab(self):
        with ui.ScrollingFrame():
            with ui.VStack(spacing=5, padding=5):
                ui.Label("1. Add Flownex Component Name to Prims", height=20, style={"font_size": 16})
                with ui.HStack(height=30):
                    ui.Label("Target Prim Path:", width=120, style={"font_size": 16})
                    self._override_target_path_field = ui.StringField(model=ui.SimpleStringModel("/World"))

                ui.Button(
                    "Start Prim Property Override",
                    clicked_fn=self._on_start_prim_property_override,
                    height=30,
                    style={"font_size": 16},
                )

                ui.Spacer(height=10)
                ui.Label("2. Generate Mapping Config File", height=20, style={"font_size": 16})
                ui.Button(
                    "Generate",
                    clicked_fn=self._on_generate_mapping_config,
                    height=30,
                    style={"font_size": 16},
                )

                ui.Spacer(height=10)
                ui.Separator()
                ui.Label("Project Import / Export:", height=20, style={"font_size": 16})
                with ui.HStack(height=30):
                    ui.Button("Import Project...", clicked_fn=self._on_import_project, width=120, style={"font_size": 16})
                    ui.Button("Export Project...", clicked_fn=self._on_export_project, width=120, style={"font_size": 16})

                ui.Spacer(height=10)
                ui.Label("Logs:", style={"font_size": 16})
                self._mapping_log_field = ui.StringField(multiline=True, height=150, read_only=True)

    def _build_results_viz_tab(self):
        with ui.ScrollingFrame():
            with ui.VStack(spacing=10, name="viz_v_stack"):
                with ui.HStack(height=25):
                    ui.Label("Property to Visualize:", width=150, style={"font_size": 16})
                    self._property_names_for_viz = get_visualizable_properties()
                    self._property_combo = ui.ComboBox(0, *self._property_names_for_viz)
                    self._property_combo.model.add_item_changed_fn(self._on_property_changed)

                with ui.HStack(height=25):
                    ui.Label("Colormap:", width=150, style={"font_size": 16})
                    self._colormap_combo = ui.ComboBox(0, *COLOR_MAP_OPTIONS)
                    self._colormap_combo.model.add_item_changed_fn(lambda *args: self._apply_coloring_for_all_keys())

                with ui.HStack(height=25, spacing=5):
                    self._manual_bounds_checkbox = ui.CheckBox(width=20, model=ui.SimpleBoolModel(False))
                    ui.Label("Set Manual Bounds", style={"font_size": 16})

                with ui.HStack(height=25, spacing=5):
                    ui.Label("Min:", width=40, style={"font_size": 16})
                    self._lower_bound_field = ui.StringField()
                    ui.Label("Max:", width=40, style={"font_size": 16})
                    self._upper_bound_field = ui.StringField()

                self._lower_bound_field.enabled = False
                self._upper_bound_field.enabled = False

                self._lower_bound_field.model.add_end_edit_fn(self._on_bounds_changed)
                self._upper_bound_field.model.add_end_edit_fn(self._on_bounds_changed)

                ui.Spacer(height=5)

                with ui.VStack(height=130):
                    ui.Label("Color Legend", style={"font_size": 20})
                    if PLOTTING_AVAILABLE:
                        self._colorbar_image_provider = ui.ByteImageProvider()
                        self._colorbar_image = ui.ImageWithProvider(self._colorbar_image_provider)
                    else:
                        ui.Label(
                            "Colorbar unavailable (matplotlib not installed)",
                            style={"color": cl.yellow, "font_size": 16},
                        )

                ui.Spacer(height=5)

                def toggle_manual_fields(use_manual):
                    is_enabled = use_manual.get_value_as_bool()
                    self._lower_bound_field.enabled = is_enabled
                    self._upper_bound_field.enabled = is_enabled

                    if is_enabled:
                        self._load_bounds_for_selected_property()

                    self._apply_coloring_for_all_keys()

                self._manual_bounds_checkbox.model.add_value_changed_fn(toggle_manual_fields)

                ui.Button(
                    "Apply/Refresh Visualization",
                    clicked_fn=self._apply_coloring_for_all_keys,
                    height=30,
                    style={"font_size": 16},
                )

                ui.Label("Visualization Logs:", style={"font_size": 16})
                self._viz_log_field = ui.StringField(multiline=True, height=150, read_only=True)

        self._current_viz_property = self._get_selected_property_name()
        self._load_bounds_for_selected_property()

    def _get_selected_property_name(self):
        try:
            index = self._property_combo.model.get_item_value_model().as_int
            if 0 <= index < len(self._property_names_for_viz):
                return self._property_names_for_viz[index]
        except Exception:
            pass
        return None

    def _save_current_property_bounds_for_name(self, prop):
        if not prop:
            return

        try:
            lower_txt = self._lower_bound_field.model.get_value_as_string().strip()
            upper_txt = self._upper_bound_field.model.get_value_as_string().strip()

            lower = float(lower_txt) if lower_txt != "" else None
            upper = float(upper_txt) if upper_txt != "" else None
        except (TypeError, ValueError):
            return

        self._property_bounds[prop] = {
            "lower": lower,
            "upper": upper,
        }

    def _save_current_property_bounds(self):
        self._save_current_property_bounds_for_name(self._get_selected_property_name())

    def _load_bounds_for_selected_property(self):
        prop = self._get_selected_property_name()
        if not prop:
            return

        bounds = self._property_bounds.get(prop, {"lower": None, "upper": None})
        lower = bounds.get("lower")
        upper = bounds.get("upper")

        self._lower_bound_field.model.set_value("" if lower is None else str(lower))
        self._upper_bound_field.model.set_value("" if upper is None else str(upper))

    def _on_property_changed(self, *args):
        if self._current_viz_property is not None:
            self._save_current_property_bounds_for_name(self._current_viz_property)

        self._current_viz_property = self._get_selected_property_name()
        self._load_bounds_for_selected_property()
        self._apply_coloring_for_all_keys()

    def _on_bounds_changed(self, model=None):
        self._save_current_property_bounds()
        self._apply_coloring_for_all_keys()

    def _apply_coloring_for_all_keys(self):
        if not hasattr(self, "_property_combo") or not hasattr(self, "_colormap_combo"):
            return

        manual_min = None
        manual_max = None
        selected_property = self._get_selected_property_name()

        if self._manual_bounds_checkbox.model.get_value_as_bool():
            bounds = self._property_bounds.get(selected_property, {})
            manual_min = bounds.get("lower")
            manual_max = bounds.get("upper")

            if manual_min is None:
                try:
                    txt = self._lower_bound_field.model.get_value_as_string().strip()
                    manual_min = float(txt) if txt != "" else None
                except (ValueError, TypeError):
                    manual_min = None

            if manual_max is None:
                try:
                    txt = self._upper_bound_field.model.get_value_as_string().strip()
                    manual_max = float(txt) if txt != "" else None
                except (ValueError, TypeError):
                    manual_max = None

        vmin, vmax, cmap, unit, newly_colored_prims = visualize_property_layer(
            log_field=getattr(self, "_viz_log_field", None),
            property_combo=self._property_combo,
            colormap_combo=self._colormap_combo,
            property_names_for_viz=self._property_names_for_viz,
            user_config=self._FlownexMain._UserSConfig,
            fnx_outputs=self._FlownexMain._fnx_outputs,
            output_fields=self._FlownexMain._outputFields,
            fnx_api=self._FlownexMain._FlownexAPI,
            prims_to_reset=self._last_colored_prims,
            manual_min_bound=manual_min,
            manual_max_bound=manual_max,
        )

        self._last_colored_prims = newly_colored_prims

        if PLOTTING_AVAILABLE and vmin is not None and hasattr(self, "_colorbar_image_provider"):
            image_data = generate_colorbar_image(vmin, vmax, cmap, unit)
            if image_data:
                self._colorbar_image_provider.set_bytes_data(*image_data)
            else:
                self._colorbar_image_provider.set_bytes_data(b"", [0, 0])
        elif hasattr(self, "_colorbar_image_provider"):
            self._colorbar_image_provider.set_bytes_data(b"", [0, 0])

    def _on_start_prim_property_override(self):
        target_path = self._override_target_path_field.model.get_value_as_string()
        if not target_path:
            msg = "Error: Target Prim Path cannot be empty."
            if hasattr(self, "_mapping_log_field"):
                self._mapping_log_field.model.set_value(msg)
            return

        msg = deinstance_and_add_flownex(target_path)
        if hasattr(self, "_mapping_log_field"):
            self._mapping_log_field.model.set_value(msg)

    def _on_generate_mapping_config(self):
        log_field = getattr(self, "_mapping_log_field", None)
        message, _ = map_outputs_to_prims(
            io_dir=self._FlownexMain._UserSConfig.Setup.IOFileDirectory,
            outputs_filename="Outputs.csv",
            out_name="FlownexMapping.json",
        )
        if log_field:
            log_field.model.set_value(message)

    def _on_export_project(self):
        from omni.kit.window.filepicker import FilePickerDialog

        def on_export_path_selected(filename, dirname):
            if filename:
                export_path = os.path.join(dirname, filename)
                export_project_to_zip(
                    export_path=export_path,
                    stage=omni.usd.get_context().get_stage(),
                    user_config=self._FlownexMain._UserSConfig,
                    log_field=getattr(self, "_mapping_log_field", None),
                )
            file_picker.hide()

        file_picker = FilePickerDialog(
            "Export Project as ZIP",
            apply_button_label="Save",
            click_apply_handler=on_export_path_selected,
            click_cancel_handler=lambda a, b: file_picker.hide(),
            item_filter_options=[".zip"],
            allow_multi_selection=False,
        )
        file_picker.show()

    def _on_import_project(self):
        from omni.kit.window.filepicker import FilePickerDialog

        def on_io_dir_selected(filename, dirname):
            io_dir_picker.hide()
            log_field = getattr(self, "_mapping_log_field", None)

            success = import_project_from_zip(
                import_path=self.zip_import_path,
                new_io_directory=dirname,
                main_settings_file=self._FlownexMain._UserSConfig.settingsFile,
                log_field=log_field,
            )

            if success:
                from .fnx_io_definition import FlownexIO

                self._FlownexMain._UserSConfig = FlownexIO()

                if hasattr(self._FlownexMain, "_io_path_field"):
                    self._FlownexMain._io_path_field.model.set_value(
                        self._FlownexMain._UserSConfig.Setup.IOFileDirectory
                    )

                if hasattr(self._FlownexMain, "_project_path_field"):
                    self._FlownexMain._project_path_field.model.set_value(
                        self._FlownexMain._UserSConfig.Setup.FlownexProject
                    )

        def on_zip_selected(filename, dirname):
            if not filename:
                zip_picker.hide()
                return

            self.zip_import_path = os.path.join(dirname, filename)
            zip_picker.hide()

            nonlocal io_dir_picker
            io_dir_picker = FilePickerDialog(
                "Select New Directory for Config Files",
                apply_button_label="Select Folder",
                click_apply_handler=on_io_dir_selected,
                click_cancel_handler=lambda a, b: io_dir_picker.hide(),
                allow_multi_selection=False,
                item_filter_fn=lambda item: item.is_folder,
            )
            io_dir_picker.show()

        io_dir_picker = None
        zip_picker = FilePickerDialog(
            "Import Project from ZIP",
            apply_button_label="Open",
            click_apply_handler=on_zip_selected,
            click_cancel_handler=lambda a, b: zip_picker.hide(),
            item_filter_options=[".zip"],
            allow_multi_selection=False,
        )
        zip_picker.show()

    def _get_plot_variable_options(self):
        if not self._FlownexMain or not self._FlownexMain._fnx_outputs:
            return []

        plot_outputs = [o for o in self._FlownexMain._fnx_outputs if getattr(o, "Category", None) == "Plot"]
        plot_output_keys = {o.Key for o in plot_outputs}

        if not self._FlownexMain.simulation_data_history:
            self._plot_key_to_label_map = {}
            return []

        history_keys = set(self._FlownexMain.simulation_data_history[0].keys())
        available_keys = sorted(list(history_keys.intersection(plot_output_keys)))

        output_defs_by_key = {o.Key: o for o in self._FlownexMain._fnx_outputs}
        self._plot_key_to_label_map = {
            key: (f"{output_defs_by_key[key].Description}" if key in output_defs_by_key else key)
            for key in available_keys
        }

        all_dropdown_keys = list(available_keys)
        if self._plot_x_axis_key not in all_dropdown_keys:
            all_dropdown_keys.insert(0, self._plot_x_axis_key)

        return all_dropdown_keys

    def _rebuild_plotting_tab(self):
        plotting_frame = self._tabs.get("plotting")
        if not plotting_frame:
            return

        # Mark as not-built before clearing so re-entrancy is safe
        self._plotting_tab_built = False
        plotting_frame.clear()

        all_keys = self._get_plot_variable_options()
        y_axis_keys = [k for k in all_keys if k != self._plot_x_axis_key]

        with plotting_frame:
            if not self._FlownexMain.simulation_data_history:
                ui.Label(
                    "No simulation data recorded. Run a simulation first.",
                    style={"color": cl.yellow, "alignment": ui.Alignment.CENTER, "font_size": 16},
                )
                # Do not mark as built – will rebuild once data arrives
                return

            if not y_axis_keys:
                ui.Label(
                    "No variables marked for plotting. Add 'Plot' to the 'Category' column in Outputs.csv.",
                    style={"color": cl.yellow, "alignment": ui.Alignment.CENTER, "font_size": 16},
                )
                # Do not mark as built – will rebuild once Plot outputs are configured
                return

            with ui.VStack():
                with ui.HStack(height=70):
                    ui.Label("X-Axis:", width=70, style={"font_size": 16})
                    all_history_keys = sorted(list(self._FlownexMain.simulation_data_history[0].keys()))
                    self._x_axis_combo = ui.ComboBox(0, *all_history_keys)
                    self._x_axis_combo.model.add_item_changed_fn(self._on_x_axis_changed)

                with ui.CollapsableFrame("Y-Axis Variables"):
                    with ui.ScrollingFrame(height=100):
                        with ui.VStack():
                            self._y_axis_checkboxes.clear()
                            for key in y_axis_keys:
                                with ui.HStack(height=20):
                                    self._y_axis_checkboxes[key] = ui.CheckBox()
                                    ui.Label(self._plot_key_to_label_map.get(key, "N/A"), style={"font_size": 16})

                ui.Spacer(height=1)
                with ui.HStack():
                    ui.Button("Add Plot", clicked_fn=self._on_add_plot_request, height=30, style={"font_size": 16})
                    ui.Button(
                        "Clear All Plots",
                        clicked_fn=self._on_clear_plots,
                        height=30,
                        style={"background_color": cl.orange, "font_size": 16},
                    )

        self._load_and_apply_plot_definitions()
        # Mark tab as fully built and record which y-keys were used
        self._plotting_tab_built = True
        self._plotting_tab_last_y_keys = frozenset(y_axis_keys)

    def _on_x_axis_changed(self, model, item_index):
        if item_index is None:
            return

        all_history_keys = sorted(list(self._FlownexMain.simulation_data_history[0].keys()))
        if item_index < len(all_history_keys):
            self._plot_x_axis_key = all_history_keys[item_index]
            self._rebuild_plotting_tab()

    def _on_add_plot_request(self):
        y_axis_keys = [k for k, cb in self._y_axis_checkboxes.items() if cb.model.get_value_as_bool()]
        if not y_axis_keys:
            return

        request = {
            "x_axis_key": self._plot_x_axis_key,
            "y_axis_keys": sorted(y_axis_keys),
        }

        if request not in self._plot_requests:
            self._plot_requests.append(request)

        self._save_plot_definitions()
        self._rebuild_and_update_plot_window()

    def _on_clear_plots(self):
        self._plot_requests.clear()
        self._save_plot_definitions()

        if self._plot_window:
            self._plot_window.destroy()
            self._plot_window = None

    def _rebuild_and_update_plot_window(self):
        """Build the plot window and all plot widgets once, then refresh data.

        Called when the user adds a new plot request (user action).  The polling
        cycle must NOT call this method – it should call _update_plot_window_data()
        instead so that only XY data is pushed into existing widgets.
        """
        if not self._plot_window or not self._plot_window.visible:
            self._plot_window = ui.Window(
                "Simulation Plot",
                width=800,
                height=700,
                closed_fn=lambda: setattr(self, "_plot_window", None),
            )
            # New window means all previously stored widget refs are stale – drop them.
            for req in self._plot_requests:
                req.pop("plot_widget", None)
                req.pop("line_plots", None)

        history = self._FlownexMain.simulation_data_history
        if not history:
            with self._plot_window.frame:
                self._plot_window.frame.clear()
                ui.Label("No simulation data to plot.", alignment=ui.Alignment.CENTER, style={"font_size": 18})
            return

        # Only do a full (expensive) rebuild when at least one request is missing its widgets.
        all_built = all(req.get("plot_widget") is not None for req in self._plot_requests)
        if not all_built:
            with self._plot_window.frame:
                self._plot_window.frame.clear()
                with ui.ScrollingFrame():
                    with ui.VStack(spacing=20, style={"padding": 10}):
                        for i, request in enumerate(self._plot_requests):
                            ui.Separator()
                            self._build_single_plot_group(i, request)

        # Refresh data in existing plot widgets (lightweight).
        self._update_plot_window_data()

    def _update_plot_window_data(self):
        if not self._plot_window or not self._plot_window.visible:
            return

        history = self._FlownexMain.simulation_data_history
        if not history:
            return

        for request in self._plot_requests:
            plot_widget = request.get("plot_widget")
            if not plot_widget:
                continue

            x_key = request["x_axis_key"]
            y_keys = request["y_axis_keys"]

            # for each y key update existing plot line
            for y_key, line_plot in request.get("line_plots", {}).items():
                data = [(d.get(x_key, 0), d.get(y_key, 0)) for d in history[-100:]]
                line_plot.set_xy_data(data)


    def _build_single_plot_group(self, index, request):
        history = self._FlownexMain.simulation_data_history[-100:]
        x_axis_key = request["x_axis_key"]
        y_axis_keys = request["y_axis_keys"]

        sorted_history = sorted(history, key=lambda d: d.get(x_axis_key, 0))

        all_y_values = []
        y_units = set()
        output_defs_by_key = {o.Key: o for o in self._FlownexMain._fnx_outputs}

        for key in y_axis_keys:
            all_y_values.extend([d.get(key, 0) for d in sorted_history])
            if key in output_defs_by_key:
                y_units.add(output_defs_by_key[key].Unit)

        y_data_min = min(all_y_values) if all_y_values else 0.0
        y_data_max = max(all_y_values) if all_y_values else 1.0
        y_data_max = max(y_data_max, y_data_min + 0.1)
        if y_data_max == y_data_min:
            y_data_max += 1.0

        y_padding = (y_data_max - y_data_min) * 0.05
        y_scale_min = y_data_min - y_padding
        y_scale_max = y_data_max + y_padding

        x_values = [d.get(x_axis_key, 0) for d in sorted_history]
        x_data_min = min(x_values) if x_values else 0.0
        x_data_max = max(x_values) if x_values else 1.0
        if x_data_max == x_data_min:
            x_data_max += 1.0

        x_padding = (x_data_max - x_data_min) * 0.05
        x_scale_min = x_data_min - x_padding
        x_scale_max = x_data_max + x_padding

        # Collect plot widget references so _update_plot_window_data() can push
        # new XY data without recreating any UI elements.
        line_plots = {}

        with ui.VStack(spacing=4, height=200):
            with ui.VStack(height=max(len(y_axis_keys) * 18, 18)):
                for key in y_axis_keys:
                    with ui.HStack(height=18):
                        ui.Spacer(width=5)
                        with ui.ZStack(height=18):
                            ui.Rectangle(style={"background_color": cl("#363636")})
                            ui.Label(
                                self._plot_key_to_label_map.get(key, key),
                                style={"font_size": 26, "color": cl("#E9E9E9"), "background_color": cl("#74B405")},
                                alignment=ui.Alignment.CENTER,
                            )

            with ui.HStack():
                self._update_y_axis_labels(y_scale_min, y_scale_max, ", ".join(y_units) or "")
                with ui.ZStack(style={"background_color": cl("#E6E6E6")}):
                    ui.Grid(ui.Direction.TOP_TO_BOTTOM, column_count=10)

                    for i, key in enumerate(y_axis_keys):
                        style = {"color": cl.black, "line_width": 25.0}
                        plot = ui.Plot(ui.Type.LINE2D, style=style)
                        data = [(d.get(x_axis_key, 0), d.get(key, 0)) for d in sorted_history]
                        plot.set_xy_data(data)
                        plot.scale_min = y_scale_min
                        plot.scale_max = y_scale_max
                        line_plots[key] = plot

            self._update_x_axis_labels(x_scale_min, x_scale_max, x_axis_key)

        # Store persistent widget references in the request dict for incremental updates.
        request["line_plots"] = line_plots
        request["plot_widget"] = True  # sentinel: widgets have been created

    def _update_y_axis_labels(self, y_min, y_max, y_units, num_ticks=5):
        with ui.VStack(width=50, spacing=0):
            ui.Label(y_units, alignment=ui.Alignment.CENTER, style={"font_size": 24.0})
            ui.Spacer()
            for i in range(num_ticks):
                val = y_max - i * (y_max - y_min) / (num_ticks - 1)
                if y_max - y_min < 0.5:
                    ui.Label(f"{val:.2f}  ", alignment=ui.Alignment.CENTER, width=50, style={"font_size": 20.0})
                else:
                    ui.Label(f"{val:.1f}  ", alignment=ui.Alignment.CENTER, width=50, style={"font_size": 20.0})

                if i < num_ticks - 1:
                    ui.Spacer()

    def _update_x_axis_labels(self, x_min, x_max, x_units, num_ticks=5):
        with ui.HStack(height=20, spacing=0):
            ui.Spacer(width=50)
            for i in range(num_ticks):
                val = x_min + i * (x_max - x_min) / (num_ticks - 1)
                with ui.VStack():
                    ui.Label(f"{val:.2f}", alignment=ui.Alignment.CENTER, style={"font_size": 16})
                if i < num_ticks - 1:
                    ui.Spacer()

            with ui.VStack():
                ui.Spacer()
                ui.Label(x_units, alignment=ui.Alignment.CENTER, style={"font_size": 16})

    def _draw_grid_lines(self, num_ticks=5):
        grid_color = cl("#6E6E6E")

        with ui.ZStack():
            with ui.Grid(ui.Direction.TOP_TO_BOTTOM, column_count=1):
                for _ in range(num_ticks):
                    with ui.Frame(height=0):
                        ui.Rectangle(height=1, style={"background_color": grid_color, "border_radius": 0})

            with ui.Grid(ui.Direction.LEFT_TO_RIGHT, row_count=1):
                for _ in range(num_ticks):
                    with ui.Frame(width=0):
                        ui.Rectangle(width=1, style={"background_color": grid_color, "border_radius": 0})

    def _on_clear_history(self):
        self._FlownexMain.simulation_data_history.clear()
        self._plot_requests.clear()
        self._save_plot_definitions()
        # Reset tab-built flag so next tab switch triggers a clean rebuild
        self._plotting_tab_built = False

        if self._plot_window and self._plot_window.visible:
            self._rebuild_and_update_plot_window()

        print("Simulation history cleared.")
        self._rebuild_plotting_tab()

    def _get_plots_file_path(self):
        io_dir = getattr(self._FlownexMain._UserSConfig.Setup, "IOFileDirectory", None)
        if not io_dir:
            return None
        return os.path.join(io_dir, "PlotSelections.json")

    def _load_and_apply_plot_definitions(self):
        plots_file_path = self._get_plots_file_path()
        self._plot_requests = []
        self._plot_x_axis_key = "Time"

        if plots_file_path and os.path.exists(plots_file_path):
            try:
                with open(plots_file_path, "r") as f:
                    data = json.load(f)
                    self._plot_requests = data.get("plot_requests", [])
                    self._plot_x_axis_key = data.get("x_axis_key", "Time")
            except (json.JSONDecodeError, IOError):
                self._plot_requests = []
                self._plot_x_axis_key = "Time"

        if self._FlownexMain.simulation_data_history and hasattr(self, "_x_axis_combo"):
            all_history_keys = sorted(list(self._FlownexMain.simulation_data_history[0].keys()))
            if self._plot_x_axis_key in all_history_keys:
                try:
                    idx = all_history_keys.index(self._plot_x_axis_key)
                    self._x_axis_combo.model.get_item_value_model().set_value(idx)
                except (ValueError, IndexError):
                    pass

        selected_y_keys = set()
        for request in self._plot_requests:
            if request.get("x_axis_key") == self._plot_x_axis_key:
                selected_y_keys.update(request.get("y_axis_keys", []))

        for key, checkbox in self._y_axis_checkboxes.items():
            checkbox.model.set_value(key in selected_y_keys)

    def _save_plot_definitions(self):
        plots_file_path = self._get_plots_file_path()
        if not plots_file_path:
            return

        data_to_save = {
            "x_axis_key": self._plot_x_axis_key,
            "plot_requests": self._plot_requests,
        }

        try:
            with open(plots_file_path, "w") as f:
                json.dump(data_to_save, f, indent=2)
        except IOError as e:
            print(f"Error saving plot selections: {e}")


    