import os
import threading
import asyncio
import omni.kit.commands
import omni.ext
import omni.ui as ui
import omni.usd
from omni.ui import color as cl
from .fnx_api import FNXApi
from .fnx_units import Unit, UnitGroup
from .fnx_io_definition import FlownexIO, InputDefinition, OutputDefinition
from typing import Optional

class FlownexMain:
    _FlownexDataTimer  = None
    _transient_running = False
    def __init__(self, ext_id: str): # <-- MODIFICATION: Add ext_id parameter
        self._ext_id = ext_id      # <-- MODIFICATION: Store ext_id
        self.ui_extension = None   # <-- MODIFICATION: Add placeholder for UI extension reference
        self._FlownexAPI = FNXApi()
        self._UserSConfig = FlownexIO()
        self._inputFields = {}   
        self._outputFields = {}
        self._input_controls = {}
        self._fnx_outputs = []
        self.simulation_data_history = []
        # Persistent result-window state (avoid frame.clear() every poll cycle)
        self._text_window = None
        self._key_params_window = None
        self._text_window_category = None   # category that was last used to build _text_window
        self._key_params_built = False      # True once _key_params_window has been fully built
        self._results_value_labels = {}     # outputDef.Key -> value ui.Label in _text_window
        self._key_params_value_labels = {}  # outputDef.Key -> value ui.Label in _key_params_window


    def _cleanup(self):
        try:     
            self.DynamicFrame = None    
            self.StaticFrame = None
            if FlownexMain._FlownexDataTimer is not None:
                FlownexMain._FlownexDataTimer.cancel()
                FlownexMain._FlownexDataTimer = None
            self._inputFields.clear()
            self._outputFields.clear()
            self._input_controls.clear()
            self._fnx_outputs.clear()
            FlownexMain._transient_running = False
            if self._FlownexAPI is not None:
                self._FlownexAPI.StopTransientSimulation()
                self._FlownexAPI.CloseProject()
                self._FlownexAPI = None
            if self._UserSConfig is not None:
                self._UserSConfig = None
        except Exception as e:
            print("Error during FlownexMain cleanup: " + str(e))
        
    #UI Construction 
    def _build_Inputs_tab(self, mode: str = "dynamic"):
        """Build the physics data reading tab"""
        self._load_flownex_outputs()
        with ui.VStack(spacing=2):             
            with ui.ScrollingFrame() as frame:        
                if( mode == "dynamic"):
                    self.DynamicFrame = frame
                else:
                    self.StaticFrame = frame
                with ui.VStack(spacing=3):
                
                    preTest: bool = True
                    #test if the Flownex API is available to report error to the user
                    if not self._FlownexAPI.IsFnxAvailable():
                        ui.Label("Flownex API not available. Please ensure Flownex is installed and the API is accessible.", style={"color": cl("#ff3333"), "font_size": 20})
                        preTest = False
                    dataSet = None
                    controls = self._input_controls
                    InputFields = self._inputFields
                    #load the user input configuration and built the inputs
                    if( mode == "dynamic"):
                        dataSet = self._UserSConfig.LoadDynamicInputs()
                        if dataSet is None or len(dataSet) == 0:
                            ui.Label("Input definition file Inputs.csv is missing or empty in "+ 
                                self._UserSConfig.Setup.IOFileDirectory + 
                                " Please configure the IO definition in the Configuration tab.", style={"color": cl("#F76C53"), "font_size": 20})
                            preTest = False
                    else:
                        dataSet = self._UserSConfig.LoadStaticInputs()
                        if dataSet is None or len(dataSet) == 0:
                            ui.Label("Input definition file StaticInputs.csv is missing or empty in "+ 
                                self._UserSConfig.Setup.IOFileDirectory + 
                                " Please configure the IO definition in the Configuration tab.", style={"color": cl("#F76C53"), "font_size": 20})
                            preTest = False
                   
                    if preTest is True:
                        InputFields.clear()
                        for inputDef in dataSet:
                            with ui.HStack(height=25):
                                if inputDef.Unit != "":
                                    unitText = "[" + inputDef.Unit + "]"
                                else:
                                    unitText = ""
                                ui.Label(f"{inputDef.Description} {unitText}:", width=300, style={"font_size": 20})
                                if inputDef.EditType == 'checkbox':
                                    checkbox = ui.CheckBox(width=20)
                                    checkbox.model.set_value(bool(inputDef.DefaultValue))
                                    checkbox.identifier = inputDef.Key
                                    InputFields[inputDef.Key] = inputDef
                                    checkbox.model.add_value_changed_fn(
                                        lambda m=checkbox.model, c=checkbox:
                                        self._on_checkbox_change(c, m.as_bool)
                                        )
                                    controls[inputDef.Key] = checkbox
                                elif inputDef.EditType == 'slider':
                                    slider = ui.FloatSlider(min=inputDef.Min, max=inputDef.Max, step=inputDef.Step, width=450,style={"font_size": 20})
                                    slider.model.set_value(inputDef.DefaultValue)
                                    slider.identifier = inputDef.Key
                                    InputFields[inputDef.Key] = inputDef
                                    slider.model.add_value_changed_fn(
                                        lambda m=slider.model, s=slider: 
                                        self._on_slider_change(s, m.as_float)
                                        )
                                    controls[inputDef.Key] = slider
                                #add other edit types here as needed
                     
                            ui.Spacer(height=5)
                        #ui.Label("Key Metrics", style={"font-size": 16, "font-weight": "bold"})

                        # Find the units from the loaded output definitions
                        # T_unit = ""
                        # P_unit= ""
                        # if self._fnx_outputs:
                        #     for out_def in self._fnx_outputs:
                        #         if out_def.Key == "T_case_1p":
                        #             T_unit = f"[{out_def.Unit}]" if out_def.Unit else ""
                        #         elif out_def.Key == "Separator_Pressure":
                        #             P_unit= f"[{out_def.Unit}]" if out_def.Unit else ""
                        
                        # with ui.VStack(spacing=3, height=0):
                        #     with ui.HStack():
                        #         ui.Label("PUE:", width=200)
                        #         ui.Spacer(width=5)
                        #         self._pue_label = ui.Label("N/A", style={"font-weight": "bold"})
                        #     with ui.HStack():
                        #         # Add the unit to the label text
                        #         ui.Label(f"Maximum Case Temperature {T_unit}:", width=200)
                        #         ui.Spacer(width=5)
                        #         self._cooling_label = ui.Label("N/A", style={"font-weight": "bold"})
                        #     with ui.HStack():
                        #         # Add the unit to the label text
                        #         ui.Label(f"Condenser Pressure {P_unit}:", width=200)
                        #         ui.Spacer(width=5)
                        #         self._heat_label = ui.Label("N/A", style={"font-weight": "bold"})
                        # ui.Spacer(height=10)

                        if( mode == "dynamic"):
                            ui.Label("Flownex Simulation Control", style={"font_size": 20})
                            with ui.HStack(height=25):
                                self._button_start_transient_simulation = ui.Button("Start Transient Simulation", width=70, height=20, style={"font_size": 20})
                                self._button_start_transient_simulation.set_clicked_fn(self.StartTransientSimulation)
                                self._button_stop_transient_simulation = ui.Button("Stop Transient Simulation", width=70, height=20, style={"font_size": 20})
                                self._button_stop_transient_simulation.set_clicked_fn(self.StopTransientSimulation)
                            with ui.HStack(height=25):
                                self._button_load_steady_state_simulation = ui.Button("Load Defaults and Solve Steady State", width=70, height=20, style={"font_size": 20})
                                self._button_load_steady_state_simulation.set_clicked_fn(self.LoadDefaultsAndSolveSteadyState)
                                self._button_steady_state_simulation = ui.Button("Solve Steady State", width=70, height=20, style={"font_size": 20})
                                self._button_steady_state_simulation.set_clicked_fn(self.RunSteadyStateSimulation)


                            self._options = self._UserSConfig.GetCategories()              

                            self._results_selection_combo = ui.ComboBox(
                                0,
                                *self._options,
                                width=300, style={"font_size": 20}
                            )

                                
                            self._results_selection_combo.model.add_item_changed_fn(
                                self._on_results_selection_changed
                            )

                    if( mode == "dynamic"):
                        ui.Label("Logs:", style={"font_size": 16})
                        self._results_field = ui.StringField(multiline=True, height=150, read_only=True)

 



    def _build_config_tab(self):
        """Build the configuration tab"""
        with ui.ScrollingFrame():
            with ui.VStack(spacing=10):
                ui.Label("Flownex Configuration", style={"font_size": 20})

                with ui.HStack(height=30):
                    ui.Label("Flownex Status", style={"font_size": 20})
                    if self._FlownexAPI.IsFnxAvailable():                                           
                        ui.Label("Flownex installation detected", style={"color": cl("#33ff33"), "font_size": 20})
                    else:
                        ui.Label("Flownex installation not detected", style={"color": cl("#ff3333"), "font_size": 20})

                with ui.HStack(height=30):
                    ui.Label("Flownex Project File:", width=150, style={"font_size": 20})
                    self._project_path_field = ui.StringField()
                    self._project_path_field.model.set_value(self._UserSConfig.Setup.FlownexProject)
                    # Add callback to update UserSetup when field changes
                    def on_project_path_changed(model):
                        self._UserSConfig.Setup.FlownexProject = model.get_value_as_string()
                        self._UserSConfig.Save()
                    self._project_path_field.model.add_end_edit_fn(on_project_path_changed)
                    self._button_flownex_project = ui.Button("...", width=30, style={"font_size": 20})
                    self.filepicker = None
                    def on_click_open_file(file, path):
                        full_file_path = os.path.join(path, file)
                        self._project_path_field.model.set_value(full_file_path)
                        self._UserSConfig.Setup.FlownexProject = full_file_path
                        self._UserSConfig.Save()
                        self.filepicker.hide()

                    def on_click_cancel_file(file, path):
                        self.filepicker.hide()

                    def on_browse_flownex_project():
                        from omni.kit.window.filepicker import FilePickerDialog
                        self.filepicker = FilePickerDialog(
                            "Select Flownex Project File", apply_button_label="Open", click_apply_handler=on_click_open_file, click_cancel_handler=on_click_cancel_file                    
                        )
                        self.filepicker.current_filename  = self._UserSConfig.Setup.FlownexProject
                        self.filepicker.file_extension_options = [(".proj", "Flownex project file"), (".projz", "Single Flownex project file"  )]
                        self.filepicker.show()
                    self._button_flownex_project.set_clicked_fn(on_browse_flownex_project)

                with ui.HStack(height=30):
                    ui.Label("IO Definition Directory:", width=150, style={"font_size": 20})
                    self._io_path_field = ui.StringField()
                    self._io_path_field.model.set_value(self._UserSConfig.Setup.IOFileDirectory)
                    # Add callback to update UserSetup when field changes
                    def on_io_path_changed(model):
                        self._UserSConfig.Setup.IOFileDirectory = model.get_value_as_string()
                        self._UserSConfig.Save()
                    self._io_path_field.model.add_end_edit_fn(on_io_path_changed)
                    self._button_io_directory = ui.Button("...", width=30, style={"font_size": 20})  
                    self.filepicker = None
                    def on_click_open_dir(file, path):
                        self._io_path_field.model.set_value(path)
                        self._UserSConfig.Setup.IOFileDirectory = path
                        self._UserSConfig.Save()
                        self.filepicker.hide()

                    def on_click_cancel_dir(file, path):
                        self.filepicker.hide()

                    def on_browse_io_directory():
                        from omni.kit.window.filepicker import FilePickerDialog
                        self.filepicker = FilePickerDialog(
                            "Select Flownex Project File", apply_button_label="Open", click_apply_handler=on_click_open_dir, click_cancel_handler=on_click_cancel_dir
                        )
                        self.filepicker.current_directory = self._UserSConfig.Setup.IOFileDirectory
                        self.filepicker.show()
                    self._button_io_directory.set_clicked_fn(on_browse_io_directory)

                with ui.HStack(height=30):
                    ui.Label("Solve on Input Change:", width=150, style={"font_size": 20})
                    self._solve_on_change_checkbox = ui.CheckBox(width=20, alignment=ui.Alignment.CENTER)
                    self._solve_on_change_checkbox.model.set_value(self._UserSConfig.Setup.SolveOnChange)
                    def on_solve_on_change(model):
                        self._UserSConfig.Setup.SolveOnChange = model.get_value_as_bool()
                        self._UserSConfig.Save()
                    self._solve_on_change_checkbox.model.add_value_changed_fn(on_solve_on_change)

                with ui.HStack(height=30):
                        ui.Label("Flownex Data Interval [s]:", width=150, style={"font_size": 20})
                        self.pollSlider = ui.FloatSlider(min=0.25, max=1.5, step=0.25, width=150)
                        self.pollSlider.model.set_value(float(self._UserSConfig.Setup.ResultPollingInterval))                       
                        self.pollSlider.model.add_value_changed_fn(self._on_poll_interval_change)

                ui.Label("Flownex API Testing:", width=150, style={"font_size": 20})
                with ui.HStack(height=30):
                    ui.Button("Open project", clicked_fn=self._open_project, width=120, style={"font_size": 20})
                    ui.Button("Close project", clicked_fn=self._close_project, width=120, style={"font_size": 20})
                    ui.Button("Close Flownex", clicked_fn=self._close_flownex, width=120, style={"font_size": 20})

                ui.Label("Logs :", style={"font_size": 20})
                self._config_results_field = ui.StringField(multiline=True, height=100, read_only=True)

    def _load_and_apply_flownex_inputs(self):
        configList = self._UserSConfig.LoadDynamicInputs()
        configList2 = self._UserSConfig.LoadStaticInputs()
        # Guard against None before attempting to merge
        if configList is None:
            configList = []
        # Merge static inputs into dynamic list (avoid duplicates)
        if configList2 is not None:
            for item in configList2:
                if item not in configList:
                    configList.append(item)
        if len(configList) == 0:
            self._append_to_results("Input definition file Inputs.csv is missing or empty in "+
                             self._UserSConfig.Setup.IOFileDirectory +
                             " Please configure the IO definition in the Configuration tab.")
            return False
        self._inputFields.clear()
        self._FlownexAPI.LaunchFlownexIfNeeded(self._UserSConfig.Setup.FlownexProject)
        for inputDef in configList:
            self._inputFields[inputDef.Key] = inputDef
            control = self._input_controls.get(inputDef.Key)
            if control:
                if inputDef.EditType == 'checkbox':
                    control.model.set_value(bool(inputDef.DefaultValue))
                elif inputDef.EditType == 'slider':
                    control.model.set_value(float(inputDef.DefaultValue))
                #add other edit types here as needed
            #set the value in Flownex as well
            
            if inputDef.Unit == None or inputDef.Unit == "":
                self._FlownexAPI.SetPropertyValue(inputDef.ComponentIdentifier, inputDef.PropertyIdentifier, str(inputDef.DefaultValue))    
            else:
                self._FlownexAPI.SetPropertyValueUnit(inputDef.ComponentIdentifier, inputDef.PropertyIdentifier, float(inputDef.DefaultValue), inputDef.Unit)
        return True

    async def _update_ui_on_main_thread(self):
            """A helper async function to ensure UI updates happen on the main thread."""
            await omni.kit.app.get_app().next_update_async()

            _fields = getattr(self, "_outputFields", {}) or {}
            
            # Get values from the output fields, defaulting to "N/A"
            _pue_val = _fields.get("PUE", "N/A")
            _T_case_1 = _fields.get("T_case_1p", "N/A")
            _Separator_Pressure = _fields.get("Separator_Pressure", "N/A")

            # Safely format values, handling potential None or non-numeric types
            _pue_text = f"{float(_pue_val):.3f}" if isinstance(_pue_val, (int, float)) else str(_pue_val)
            _T_case_1_text = f"{float(_T_case_1):.2f}" if isinstance(_T_case_1, (int, float)) else str(_T_case_1)
            _Separator_Pressure_text = f"{float(_Separator_Pressure):.2f}" if isinstance(_Separator_Pressure, (int, float)) else str(_Separator_Pressure)

            # Determine color based on whether the value is valid
            good_color = cl("#33ff33") # Green
            bad_color = cl("#ff3333")  # Red

            if hasattr(self, "_pue_label") and self._pue_label:
                self._pue_label.text = _pue_text
                self._pue_label.style = {"color": good_color if _pue_text != "N/A" else bad_color, "font_size": 20}
            if hasattr(self, "_cooling_label") and self._cooling_label:
                self._cooling_label.text = _T_case_1_text 
                self._cooling_label.style = {"color": good_color if _T_case_1_text != "N/A" else bad_color, "font_size": 20}
            if hasattr(self, "_heat_label") and self._heat_label:
                self._heat_label.text = _Separator_Pressure_text
                self._heat_label.style = {"color": good_color if _Separator_Pressure_text != "N/A" else bad_color, "font_size": 20}

    def _update_ui_after_data_pull(self):
        """Called on the main thread after every Flownex data fetch.

        Responsibilities:
          - Schedule lightweight label updates via the async helper.
          - Refresh the Component Results / Key Parameters windows.
          - Trigger _update_ui_and_visualization() on the UI extension so that:
              * USD prim colors are updated with the latest output values.
              * Open plot windows receive new data points.
        """
        asyncio.ensure_future(self._update_ui_on_main_thread())

        # Refresh the results display windows (incremental, no frame.clear()).
        self._UpdateResultsWindow()

        # Update visualization colors and plot data with the new fetch results.
        if hasattr(self, "ui_extension") and self.ui_extension:
            self.ui_extension._update_ui_and_visualization()

    def _flownex_step(self):  
        if FlownexMain._FlownexDataTimer is not None and FlownexMain._transient_running:
            try:
                FlownexMain._FlownexDataTimer.cancel()
                self._fetch_flownex_results()
                self.eventLoop.call_soon_threadsafe(self._update_ui_after_data_pull)
                #incase user changed the polling interval with slider, update the timer interval
                FlownexMain._FlownexDataTimer = threading.Timer(float(self._UserSConfig.Setup.ResultPollingInterval), self._flownex_step)
                FlownexMain._FlownexDataTimer.start()
            except Exception as e:            
                self.eventLoop.call_soon_threadsafe(self._append_to_results, "Error fetching Flownex results: " + str(e))

    #for now just use a thread timer to poll the data
    #in future, use the omniver frame API
    def StartTransientSimulation(self):
        if not self._load_flownex_outputs():
            return     
        self.eventLoop = asyncio.get_event_loop()    
        self._FlownexAPI.LaunchFlownexIfNeeded(self._UserSConfig.Setup.FlownexProject)
        self._FlownexAPI.StartTransientSimulation()
        FlownexMain._transient_running = True
        FlownexMain._FlownexDataTimer = threading.Timer(float(self._UserSConfig.Setup.ResultPollingInterval), self._flownex_step)
        FlownexMain._FlownexDataTimer.start()
        self._button_start_transient_simulation.enabled = False
        self._button_stop_transient_simulation.enabled = True
        self._button_load_steady_state_simulation.enabled = False
        self._button_steady_state_simulation.enabled = False
        self.StaticFrame.enabled = False

    def StopTransientSimulation(self):     
        FlownexMain._transient_running = False   
        if FlownexMain._FlownexDataTimer is not None:
            self._FlownexAPI.StopTransientSimulation()
            FlownexMain._FlownexDataTimer.cancel()
            FlownexMain._FlownexDataTimer = None
        self._button_start_transient_simulation.enabled = True
        self._button_stop_transient_simulation.enabled = False
        self._button_load_steady_state_simulation.enabled = True
        self._button_steady_state_simulation.enabled = True    
        self.StaticFrame.enabled = True

    def _solving_completed(self, success: bool, errorMessage: str = ""):
        self.DynamicFrame.enabled = True
        self.StaticFrame.enabled = True    
        if not success:
            self._append_to_results("Steady state simulation failed " + errorMessage)
            #return  #todo, enable this line when the API is fixed

        # This was calling _UpdateResultsWindow before, now it's handled by the main update method.
        # Let's ensure the main update method is called which now handles both windows.
        self._update_ui_after_data_pull()
        
        #as agreed, for now just write the ouptuts in the log window
        self._results_field.model.set_value("")        
        #write outptuts in key value format to  ._append_to_results
        self._append_to_results("Simulation completed. Outputs:")
        for key, value in self._outputFields.items():
            self._append_to_results(f"{key}: {value}")        

    
    def _fetch_flownex_results(self):     
        current_data_point = {}
        for outputDef in self._fnx_outputs:
            value = None
            if outputDef.Unit is not None and outputDef.Unit != "":
                value = self._FlownexAPI.GetPropertyValueUnit(outputDef.ComponentIdentifier, outputDef.PropertyIdentifier, outputDef.Unit)
            else:
                str_value = self._FlownexAPI.GetPropertyValue(outputDef.ComponentIdentifier, outputDef.PropertyIdentifier)
                if str_value is not None:
                    try:
                        value = float(str_value)
                    except (ValueError, TypeError):
                        value = str_value
            
            if value is not None:
                self._outputFields[outputDef.Key] = value
                current_data_point[outputDef.Key] = value # Capture for history

        if current_data_point:
            time_step = float(self._UserSConfig.Setup.ResultPollingInterval)
            # If history is empty, time starts at 0. Otherwise increment from the last recorded time.
            last_time = self.simulation_data_history[-1].get("Time", -time_step) if self.simulation_data_history else -time_step
            current_data_point["Time"] = last_time + time_step
            self.simulation_data_history.append(current_data_point)

            max_history = 300
            if len(self.simulation_data_history) > max_history:
                self.simulation_data_history = self.simulation_data_history[-max_history:]

    def _load_flownex_outputs(self):
        self._fnx_outputs = self._UserSConfig.LoadOutputs()
        if self._fnx_outputs  is None or len(self._fnx_outputs ) == 0:
            self._append_to_results("Output definition file Outputs.csv is missing or empty "+ 
                             self._UserSConfig.Setup.IOFileDirectory + 
                             " Please configure the IO definition in the Configuration tab.")
            return False
        return True

    def LoadDefaultsAndSolveSteadyState(self):
        if not self._load_and_apply_flownex_inputs():
            return
        self.RunSteadyStateSimulation()

    def RunSteadyStateSimulation(self):
        #clear history in output that user can see new error messages
        self._FlownexAPI.LaunchFlownexIfNeeded(self._UserSConfig.Setup.FlownexProject)
        #clear results display
        self._results_field.model.set_value("")
        if not self._load_flownex_outputs():
            return           
        self.eventLoop = asyncio.get_event_loop()    
        def solver_thread():   
            
            try:                        
                self._flownex_solve_success = self._FlownexAPI.RunSteadyStateSimulationBlocking()
                self._solver_done = True                 
                if self._flownex_solve_success:
                    self._fetch_flownex_results()
                self.eventLoop.call_soon_threadsafe(self._solving_completed, self._flownex_solve_success, "")
            except Exception as e:
                self.eventLoop.call_soon_threadsafe(self._solving_completed, self._flownex_solve_success, str(e))
    
                

        self._outputFields.clear()
        self._append_to_results("Running Flownex steady state simulation...")   
        self._solver_done = False
        self._flownex_solve_success = False
        self.DynamicFrame.enabled = False
        self.StaticFrame.enabled = False
        threading.Thread(target=solver_thread, daemon=True).start()

    #slider callback
    def _on_slider_change(self,slider, value: float):
       
        data = self._inputFields.get(slider.identifier)
        if data:
            self._FlownexAPI.LaunchFlownexIfNeeded(self._UserSConfig.Setup.FlownexProject)
            if data.Unit == None or data.Unit == "":
                self._FlownexAPI.SetPropertyValue(data.ComponentIdentifier, data.PropertyIdentifier, str(value))    
            else:
                self._FlownexAPI.SetPropertyValueUnit(data.ComponentIdentifier, data.PropertyIdentifier, value, data.Unit)
            if self._UserSConfig.Setup.SolveOnChange is True:
               self.RunSteadyStateSimulation()

    
    def _on_checkbox_change(self,checkbox, value: bool):       
        data = self._inputFields.get(checkbox.identifier)
        if data:
            self._FlownexAPI.LaunchFlownexIfNeeded(self._UserSConfig.Setup.FlownexProject)
            value = "1" if value else "0" #depends on windows system language. If this fails, ask the system language and set accordingly
            self._FlownexAPI.SetPropertyValue(data.ComponentIdentifier, data.PropertyIdentifier, str(value))
            if self._UserSConfig.Setup.SolveOnChange is True:
                self.RunSteadyStateSimulation()

   

    def _on_results_selection_changed(self, box, index):
        """Callback when combobox value changes"""
        self._UpdateResultsWindow()

   
    def _UpdateResultsWindow(self):
        if not self._options or not self._results_selection_combo:
            return
            
        label_index_str = self._results_selection_combo.model.get_item_value_model().as_string
        if not label_index_str:
            return
        
        label_index = int(label_index_str)
        if label_index >= len(self._options):
            return

        label = self._options[label_index]
        text_label = f"Results: {label}"

        headers = ["Variable", "Value"]

        # --- Helper: create a styled cell and return the inner Label widget ---
        def _cell(text, header=False):
            bg = cl("#134d67") if header else cl(0.16)
            fg = cl("#ffffff") if header else cl("#eaeaea")
            border = cl(0.35)
            with ui.Frame(style={
                "background_color": bg,
                "border_color": border,
                "border_width": 1.0,
                "padding": 6,
            }):
                lbl = ui.Label(str(text), style={"color": fg, "font_size": 20})
            return lbl

        # --- Helper: compute display value for a single output definition ---
        def _display(outputDef):
            raw_val = self._outputFields.get(outputDef.Key)
            if raw_val is None:
                return "N/A"
            try:
                return (str(round(float(raw_val), 2)) + " " + (outputDef.Unit or "")).strip()
            except (ValueError, TypeError):
                return f"err({raw_val})"

        # ------------------------------------------------------------------ #
        # WINDOW 1 – component results for the currently selected category    #
        # ------------------------------------------------------------------ #
        window1_new = not self._text_window or not self._text_window.visible
        if window1_new:
            self._text_window = ui.Window("Component Results", width=760, height=520)
            # Force a full build on the new window
            self._text_window_category = None
            self._results_value_labels = {}

        category_changed = (label != self._text_window_category)

        if category_changed:
            # Build the window content once for this category
            self._text_window_category = label
            self._results_value_labels = {}

            with self._text_window.frame:
                self._text_window.frame.clear()
                with ui.VStack(height=ui.Percent(100), spacing=8):
                    self._result_label_name = ui.Label(text_label, style={"font_size": 22.0})
                    ui.Spacer(height=5)
                    scroll = ui.ScrollingFrame(
                        vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON,
                        horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                        height=ui.Percent(100),
                    )
                    with scroll:
                        grid = ui.VGrid(column_count=2)
                        with grid:
                            for h in headers:
                                _cell(h, header=True)
                            for outputDef in self._fnx_outputs:
                                if outputDef.Category == label:
                                    _cell(str(outputDef.Description), header=False)
                                    val_lbl = _cell(_display(outputDef), header=False)
                                    self._results_value_labels[outputDef.Key] = val_lbl
        else:
            # Same category – only update the text in existing value labels
            if getattr(self, "_result_label_name", None):
                self._result_label_name.text = text_label
            for outputDef in self._fnx_outputs:
                if outputDef.Category == label:
                    val_lbl = self._results_value_labels.get(outputDef.Key)
                    if val_lbl:
                        val_lbl.text = _display(outputDef)

        # ------------------------------------------------------------------ #
        # WINDOW 2 – key parameters (outputs whose category == "Plot")        #
        # ------------------------------------------------------------------ #
        window2_new = not self._key_params_window or not self._key_params_window.visible
        if window2_new:
            self._key_params_window = ui.Window("Key Parameters", width=420, height=360)
            self._key_params_built = False
            self._key_params_value_labels = {}

        if not self._key_params_built:
            # Build the key-parameters window once
            self._key_params_value_labels = {}
            with self._key_params_window.frame:
                self._key_params_window.frame.clear()
                with ui.VStack(height=ui.Percent(100), spacing=8):
                    ui.Label("Key Parameters", style={"font_size": 22.0})
                    scroll2 = ui.ScrollingFrame(
                        vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON,
                        horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                        height=ui.Percent(100),
                    )
                    with scroll2:
                        grid2 = ui.VGrid(column_count=2)
                        with grid2:
                            for h in headers:
                                _cell(h, header=True)
                            for outputDef in self._fnx_outputs:
                                if isinstance(outputDef.Category, str) and outputDef.Category.lower() == "plot":
                                    _cell(str(outputDef.Description), header=False)
                                    val_lbl = _cell(_display(outputDef), header=False)
                                    self._key_params_value_labels[outputDef.Key] = val_lbl
            self._key_params_built = True
        else:
            # Only update the value labels in the existing grid
            for outputDef in self._fnx_outputs:
                if isinstance(outputDef.Category, str) and outputDef.Category.lower() == "plot":
                    val_lbl = self._key_params_value_labels.get(outputDef.Key)
                    if val_lbl:
                        val_lbl.text = _display(outputDef)



    def _on_poll_interval_change(self, value: float):
        self._UserSConfig.Setup.ResultPollingInterval = str(value.as_float)
        self._UserSConfig.Save()


    def _close_flownex(self):
        if self._FlownexAPI is not None:
            self._FlownexAPI.ExitApplication()
            
    def _close_project(self):
        if self._FlownexAPI is not None:
            self._FlownexAPI.CloseProject()

    def _open_project(self):
        if self._FlownexAPI is not None:
            self._FlownexAPI.LaunchFlownexIfNeeded(self._UserSConfig.Setup.FlownexProject)

    def _append_to_results(self, message):
        """Append a message to the results field, with a newline."""
        current_model = getattr(self, "_results_field", None)
        if current_model is None:
            return
        
        current = current_model.model.get_value_as_string()
        current += message + "\n"
        current_model.model.set_value(current)