# In flownex_attr_tools.py

# In flownex_attr_tools.py

def deinstance_and_add_flownex(root="/World"):
    """
    De-instances prims and adds a custom 'flownex:componentName' attribute
    under a 'Flownex' display group for better visibility.
    """
    from pxr import Usd, Sdf
    import omni.usd

    st = omni.usd.get_context().get_stage()
    if not st:
        return "No stage loaded."

    # --- Step 1: De-instance prims (no change) ---
    deinstanced = 0
    for prim in st.Traverse():
        p = prim.GetPath().pathString
        if p.startswith(root) and prim.IsInstance():
            prim.SetInstanceable(False)
            deinstanced += 1

    # --- Step 2: Add the custom attribute with a displayGroup ---
    st.SetEditTarget(Usd.EditTarget(st.GetRootLayer()))
    added = 0
    with Sdf.ChangeBlock():
        for prim in st.Traverse():
            if not prim.IsValid() or not prim.GetPath().pathString.startswith(root) or prim.IsInstanceProxy() or not prim.IsDefined():
                continue
            
            # If the attribute already exists, just skip this prim
            if prim.HasAttribute("flownex:componentName"):
                continue
            
            # Create the attribute
            attr = prim.CreateAttribute("flownex:componentName", Sdf.ValueTypeNames.String, custom=True)
            
            # --- This is the simple, reliable line that works ---
            # It creates the "Flownex" group inside "Raw USD Properties"
            attr.SetMetadata('displayGroup', 'Flownex')
            added += 1

    # --- Step 3: Count prims that have a name assigned ---
    final_named_count = 0
    for prim in st.Traverse():
        if not prim.IsValid() or not prim.GetPath().pathString.startswith(root):
            continue
        a = prim.GetAttribute("flownex:componentName")
        if a and a.Get():
            final_named_count += 1

    return f"De-instanced {deinstanced}, added Flownex attribute to {added} prims. Total prims with name: {final_named_count}."




def map_outputs_to_prims(io_dir, outputs_filename="Outputs.csv", root="/World", out_name="FlownexMapping.json"):
    """
    Builds a mapping from Flownex components to a list of USD prim paths
    by matching 'ComponentIdentifier'. Supports one-to-many mappings.
    """
    import os, csv, json
    import omni.usd

    def _norm(s: str) -> str:
        return "".join((s or "").split()).lower()

    st = omni.usd.get_context().get_stage()
    if not st:
        return "No stage loaded.", None

    csv_path = os.path.join(io_dir, outputs_filename)
    if not os.path.isfile(csv_path):
        return f"Missing {csv_path}", None

    # --- MODIFICATION START: Prepare to store a list of paths ---
    components_to_map = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "ComponentIdentifier" not in reader.fieldnames:
            return "Outputs.csv is missing the 'ComponentIdentifier' column.", None
        for row in reader:
            cid = (row.get("ComponentIdentifier") or "").strip()
            if cid:
                # Initialize with an empty list to hold prim paths
                components_to_map[cid] = []
    # --- MODIFICATION END ---

    want_norm_to_cid = {_norm(cid): cid for cid in components_to_map}
    
    matched_prim_count = 0
    for prim in st.Traverse():
        if not prim.IsValid() or not prim.GetPath().pathString.startswith(root) or prim.IsInstanceProxy():
            continue

        # Only match prims where the user has explicitly assigned a non-empty
        # flownex:componentName value.  Prims that merely have the attribute
        # created (but left blank) and prims that never had the attribute added
        # are intentionally skipped – they should never be colored.
        if not prim.HasAttribute("flownex:componentName"):
            continue
        name_to_match = prim.GetAttribute("flownex:componentName").Get()
        if not name_to_match:
            continue

        norm_name = _norm(str(name_to_match))
        if norm_name in want_norm_to_cid:
            original_cid = want_norm_to_cid[norm_name]
            # --- MODIFICATION: Always append the matched prim path to the list ---
            components_to_map[original_cid].append(prim.GetPath().pathString)
            matched_prim_count += 1
            # --- MODIFICATION END ---
    
    out_path = os.path.join(io_dir, out_name)

    # We will now always output JSON as it natively supports lists.
    # We filter out any components that didn't have any prims mapped.
    final_mapping = {cid: paths for cid, paths in components_to_map.items() if paths}
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_mapping, f, indent=2)
        
    mapped_component_count = len(final_mapping)
    total_components = len(components_to_map)
    
    return f"Mapped {mapped_component_count}/{total_components} components to {matched_prim_count} prims -> {out_path}", out_path


def get_io_dir_from_local_json():
    """Return IOFileDirectory from FlownexUser.json located next to this module."""
    import os, json
    json_path = os.path.join(os.path.dirname(__file__), "FlownexUser.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("IOFileDirectory")
    except Exception:
        return None


def read_component_identifiers(io_dir, outputs_filename="Outputs.csv"):
    """Return a list of non-empty ComponentIdentifier values from the CSV."""
    import os, csv
    ids = []
    csv_path = os.path.join(io_dir, outputs_filename)
    try:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            key = next((h for h in r.fieldnames if h.strip().lower() == "componentidentifier"), None)
            if key:
                for row in r:
                    v = (row.get(key) or "").strip()
                    if v:
                        ids.append(v)
    except Exception:
        return []
    return ids


def export_project_to_zip(export_path, stage, user_config, log_field):
    """Zips the current USD scene and all associated config files into a single file."""
    import zipfile
    import os
    import shutil

    if not log_field:
        print("Log field not provided for export.")
        return

    log_field.model.set_value(f"Exporting project to {export_path}...\n")

    try:
        if not stage:
            log_field.model.set_value("Error: No active stage to export.\n")
            return
        
        temp_dir = os.path.join(os.path.dirname(export_path), "temp_export")
        os.makedirs(temp_dir, exist_ok=True)
        temp_usd_path = os.path.join(temp_dir, "scene.usda")
        stage.GetRootLayer().Export(temp_usd_path)
        log_field.model.set_value(log_field.model.get_value_as_string() + f"Saved scene to {temp_usd_path}\n")

        io_dir = user_config.Setup.IOFileDirectory
        config_files = {
            "FlownexUser.json": user_config.settingsFile,
            "Inputs.csv": os.path.join(io_dir, "Inputs.csv"),
            "Outputs.csv": os.path.join(io_dir, "Outputs.csv"),
            "FlownexMapping.json": os.path.join(io_dir, "FlownexMapping.json"),
        }

        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(temp_usd_path, arcname="scene.usda")
            for name, path in config_files.items():
                if os.path.exists(path):
                    zipf.write(path, arcname=name)
                    log_field.model.set_value(log_field.model.get_value_as_string() + f"Added {name}\n")
                else:
                    log_field.model.set_value(log_field.model.get_value_as_string() + f"Warning: {name} not found.\n")

        log_field.model.set_value(log_field.model.get_value_as_string() + "\nExport successful!")

    except Exception as e:
        log_field.model.set_value(f"An error occurred during export: {e}")
    finally:
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def import_project_from_zip(import_path, new_io_directory, main_settings_file, log_field):
    """Unzips a project file, loads the USD, and copies config files."""
    import zipfile
    import shutil
    import os
    import json
    import omni.usd

    if not log_field:
        print("Log field not provided for import.")
        return False
        
    log_field.model.set_value(f"Importing from {import_path}...\n")

    try:
        temp_dir = os.path.join(os.path.dirname(import_path), "temp_import")
        os.makedirs(temp_dir, exist_ok=True)

        with zipfile.ZipFile(import_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        log_field.model.set_value(log_field.model.get_value_as_string() + "Archive extracted.\n")

        usd_path = os.path.join(temp_dir, "scene.usda")
        if os.path.exists(usd_path):
            omni.usd.get_context().open_stage(usd_path)
            log_field.model.set_value(log_field.model.get_value_as_string() + f"Opened stage: {usd_path}\n")
        else:
            raise FileNotFoundError("scene.usda not found in the zip archive.")

        os.makedirs(new_io_directory, exist_ok=True)
        config_filenames = ["Inputs.csv", "Outputs.csv", "FlownexMapping.json"]
        for fname in config_filenames:
            src = os.path.join(temp_dir, fname)
            if os.path.exists(src):
                shutil.copy(src, new_io_directory)
                log_field.model.set_value(log_field.model.get_value_as_string() + f"Copied {fname}\n")

        user_settings_path = os.path.join(temp_dir, "FlownexUser.json")
        if os.path.exists(user_settings_path):
            with open(user_settings_path, 'r') as f:
                settings_data = json.load(f)
            
            settings_data["IOFileDirectory"] = new_io_directory
            
            with open(main_settings_file, 'w') as f:
                json.dump(settings_data, f)
            
            log_field.model.set_value(log_field.model.get_value_as_string() + "Updated main configuration.\n")

        log_field.model.set_value(log_field.model.get_value_as_string() + "\nImport successful! Please rebuild the UI by switching tabs.\n")
        return True

    except Exception as e:
        log_field.model.set_value(f"An error occurred during import: {e}")
        return False
    finally:
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)