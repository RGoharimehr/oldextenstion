"""
Base classes for SimReady component simulation system
"""
from typing import Dict, List, Optional, Any, Callable
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum


import csv
import json
import os

def my_custom_converter(obj):
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    raise TypeError

@dataclass
class UserSetupStore:
    IOFileDirectory = ""
    FlownexProject = ""
    SolveOnChange = False
    ResultPollingInterval = "1.0"  #seconds

class EditorType(Enum):
    """Types of data that can flow through ports"""
    SLIDER = "slider"
    CHECKBOX = "checkbox"


@dataclass
class InputDefinition:
    Key: str
    Description: str
    ComponentIdentifier: str
    PropertyIdentifier: str
    EditType: EditorType
    Min: float = 0.0
    Max: float = 10000000
    Step: float = 1.0
    Unit: str = ""
    DefaultValue: float = 0.0

@dataclass
class OutputDefinition:
    Category: str
    Key: str  # unique key to identify the output
    Description: str  #if needed in future
    ComponentIdentifier: str
    PropertyIdentifier: str
    Unit: str = ""
   

class FlownexIO:
   
    settingsFile: str
    UserSetup = None
        
    #For now, store the settings just next to __file__. 
    def __init__(self):
        self.UserSetup = UserSetupStore()
        current_directory = os.path.dirname(os.path.abspath(__file__))
        self.settingsFile = os.path.join(current_directory, "FlownexUser.json")
        if(os.path.exists(self.settingsFile)):
            with open(self.settingsFile, 'r') as file:
                content = file.read()
            x = json.loads(content, object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))
            self.UserSetup.FlownexProject = x.FlownexProject
            self.UserSetup.IOFileDirectory = x.IOFileDirectory
            self.UserSetup.SolveOnChange = x.SolveOnChange
            self.UserSetup.ResultPollingInterval = "1.0"
            #handle older files that do not have ResultPollingInterval
            try:
                self.UserSetup.ResultPollingInterval = x.ResultPollingInterval
            except:
                pass

    def Save(self):
        jsonTxt = json.dumps(self.UserSetup.__dict__)
        with open(self.settingsFile, 'w') as file:
            file.write(jsonTxt)

        # if the file Inputs.csv in IOFileDirectory does not exist, create it with header row
        #then the user can edit it better
        inputFile = os.path.join(self.UserSetup.IOFileDirectory, "Inputs.csv")
        if not os.path.exists(inputFile):
            with open(inputFile, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Key', 'Description', 'ComponentIdentifier', 'PropertyIdentifier', 'EditType', 'Min', 'Max', 'Step', 'Unit', 'DefaultValue'])

        outputFile = os.path.join(self.UserSetup.IOFileDirectory, "Outputs.csv")
        if not os.path.exists(outputFile):
            with open(outputFile, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Key', 'Description', 'ComponentIdentifier', 'PropertyIdentifier', 'Unit'])
   
        staticInputsFile = os.path.join(self.UserSetup.IOFileDirectory, "StaticInputs.csv")
        if not os.path.exists(staticInputsFile):
            with open(staticInputsFile, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Key', 'Description', 'ComponentIdentifier', 'PropertyIdentifier', 'Unit', 'Value'])

    @property 
    def Setup(self): 
        return self.UserSetup 
    
    def LoadAnInputFile(self, filePath: str) -> Optional[List[InputDefinition]]:
        if not os.path.exists(filePath):
            print("No IO data definition file found: " + filePath)
            return None
        inputs: List[InputDefinition] = []
        with open(filePath, encoding='utf-8-sig', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    default_value = row['DefaultValue']

                    if row['EditType'] == 'checkbox':
                        # Convert to a boolean (handles "True"/"False", "1"/"0", etc.)
                        default_value = str(default_value).lower() in ("true", "1", "yes", "y")
                    else:
                        default_value = float(default_value) if default_value not in (None, "") else 0.0

                    inputDef = InputDefinition(
                        Key=row['Key'],
                        Description=row['Description'],
                        ComponentIdentifier=row['ComponentIdentifier'],
                        PropertyIdentifier=row['PropertyIdentifier'],
                        EditType=row['EditType'],
                        Min=float(row['Min']) if row.get('Min') else 0.0,
                        Max=float(row['Max']) if row.get('Max') else 10000000,
                        Step=float(row['Step']) if row.get('Step') else 1.0,
                        Unit=row['Unit'],
                        DefaultValue=default_value,
                    )
                    #add validation here because a user can easilly write wrong data in the csv
                    #test if Min, Max, step, DefaultValue,  are valid floats
                    if not all(isinstance(x, float) for x in [inputDef.Min, inputDef.Max, inputDef.Step]):
                        print(f"Invalid float values for input {inputDef.Key}.")
                        continue
                    #test if EditType is valid
                    if inputDef.EditType not in ['slider', 'checkbox']:
                        print(f"Invalid EditType for input {inputDef.Key}. Should be 'slider' or 'checkbox'.")
                        continue
                    if inputDef.EditType == 'slider':
                        if inputDef.Min >= inputDef.Max:
                            print(f"Invalid Min/Max values for input {inputDef.Key}. Min should be less than Max.")
                            continue
                        if  inputDef.Step <= 0:
                            print(f"Invalid Step value for input {inputDef.Key}. Step should be greater than 0.")
                            continue
                        #test that DefaultValue is between Min and Max
                        if not (inputDef.Min <= inputDef.DefaultValue <= inputDef.Max):
                            print(f"Invalid DefaultValue for input {inputDef.Key}. Should be between Min and Max.")
                            continue
                    #test that Key, Description, ComponentIdentifier, PropertyIdentifier are not empty
                    if not all(isinstance(x, str) and x.strip() for x in [inputDef.Key, inputDef.Description, inputDef.ComponentIdentifier, inputDef.PropertyIdentifier]):
                        print(f"Key, Description, ComponentIdentifier, and PropertyIdentifier must be non-empty strings for input {inputDef.Key}.")
                        continue

                    inputs.append(inputDef)
                except KeyError as e:
                    print(f"Missing expected column in CSV: {e}")       
                except ValueError as e:
                    print(f"Invalid data format in CSV: {e}")


        return inputs
    
    def LoadDynamicInputs(self):
        if self.UserSetup.IOFileDirectory == "":
            print("No IO data definition directory specified")
            return None
        #load csv file named Inputs.csv from self.UserSetup.IOFileDirectory into a list of InputDefinition
        inputFile = os.path.join(self.UserSetup.IOFileDirectory, "Inputs.csv")
        dynamicInputs = self.LoadAnInputFile(inputFile)
        return dynamicInputs

    def LoadStaticInputs(self):
        if self.UserSetup.IOFileDirectory == "":
            print("No IO data definition directory specified")
            return None
        #load csv file named StaticInputs.csv from self.UserSetup.IOFileDirectory into a list of InputDefinition
        staticInputFile = os.path.join(self.UserSetup.IOFileDirectory, "StaticInputs.csv")
        staticInputs = self.LoadAnInputFile(staticInputFile)
        return staticInputs

    def LoadOutputs(self):
        if self.UserSetup.IOFileDirectory == "":
            print("No IO data definition directory specified")
            return None
        #load csv file named Outputs.csv from self.UserSetup.IOFileDirectory into a list of OutputDefinition
        outputFile = os.path.join(self.UserSetup.IOFileDirectory, "Outputs.csv")
        if not os.path.exists(outputFile):
            print("No IO data definition file found: " + outputFile)
            return None
        outputs: List[OutputDefinition] = []
        with open(outputFile, 'r', encoding='utf-8-sig', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    # outputDef = OutputDefinition(
                    #     Category=row['Category'],
                    #     Key=row['Key'],
                    #     Description=row['Description'],
                    #     ComponentIdentifier=row['ComponentIdentifier'],
                    #     PropertyIdentifier=row['PropertyIdentifier'],
                    #     Unit=row['Unit'],
                    # )
                    # Trim whitespace from important fields to avoid accidental "space" values
                    category = (row.get('Category') or "").strip()
                    key = (row.get('Key') or "").strip()
                    desc = (row.get('Description') or "").strip()
                    comp = (row.get('ComponentIdentifier') or "").strip()
                    prop = (row.get('PropertyIdentifier') or "").strip()
                    unit = (row.get('Unit') or "").strip()

                    outputDef = OutputDefinition(
                        Category=category,
                        Key=key,
                        Description=desc,
                        ComponentIdentifier=comp,
                        PropertyIdentifier=prop,
                        Unit=unit,
                    )
                    
                    outputs.append(outputDef)
                except KeyError as e:
                    print(f"Missing expected column in CSV: {e}")
                except ValueError as e:
                    print(f"Invalid data format in CSV: {e}")

        return outputs
    
    def GetCategories(self) -> List[str]:
        outputs = self.LoadOutputs()
        if outputs is None:
            return []
        #set() messes order up. Want to keep category order as definded in csv
        categories = []
        for output in outputs:
            if output.Category not in categories:
                categories.append(output.Category)
        return categories