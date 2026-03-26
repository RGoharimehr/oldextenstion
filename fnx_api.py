"""
Base classes for SimReady component simulation system
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from .fnx_units import BaseUnit, Unit, UnitGroup

#why does adding pythonnet in toml file section [python.pipapi] not work?
import omni.kit.pipapi
omni.kit.pipapi.install(
    package="pythonnet",    
    module="clr", # sometimes module is different from package name, module is used for import check
    ignore_import_check=False,
    ignore_cache=False,
    use_online_index=True,
    surpress_output=False,
    extra_args=[]
)   

import clr
import Microsoft.Win32
import os


class FNXApi:
    """Class to managed Flownex API"""        

# Get Flownex last COM API registerred installation location return "" when not found
    def GetFlownexDirectory(self):
        classesRoot = Microsoft.Win32.RegistryKey.OpenBaseKey(Microsoft.Win32.RegistryHive.ClassesRoot, Microsoft.Win32.RegistryView.Default)
        clsidRoot = classesRoot.OpenSubKey('CLSID')
        fnxKey = clsidRoot.OpenSubKey('{FD40D175-FED4-4619-8571-36336DD2B8E1}')
        if fnxKey is not None:
            localServerKey = fnxKey.OpenSubKey('LocalServer32')
            value = str(localServerKey.GetValue(None))
            value = value.replace(' /automation', '')
            #print("Flownex location: " + value)
            value = value.rpartition('FlownexSE.exe')[0]
            if value is None:
                print("Could not resolve Flownex registration. Run the 'registercomapi.bat' (found in the correct version's Program Files)")
            return value
        else:
            print("Could not resolve Flownex key in registry")
            print("Run the 'registercomapi.bat' (found in the Flownex installation folder in Program Files)")
        return None    
    
    def __init__(self):
        self.ProjectFile: str
        self.FlownexInstallationDetected = False
        self.AttachedProject = None
        self.FlownexSE = None
        self.SimulationController = None
        self.NetworkBuilder = None
        FlownexPath = self.GetFlownexDirectory()
        self._property_cache: Dict[str, Any] = {}
        if FlownexPath is not None and FlownexPath != '':            
            try:
                clr.AddReference(FlownexPath + 'IPS.Core.dll')
                import IPS
                from IPS import Core
                self.FlownexInstallationDetected = True
            except  Exception as e:
                print(f"Error loading Flownex API module IPS.Core.dll: {e}")

    def AttachToProject(self, projectPath: str):
        if not self.FlownexInstallationDetected:
            print("Flownex not available")
            return None
        
        #if if project path changed, close old project and open new one
        if self.AttachedProject is not None and self.ProjectFile != "" and self.ProjectFile != projectPath:
            self.CloseProject()

        if self.AttachedProject is not None:
            print("Flownex already attached")
            return            

        if not os.path.isfile(projectPath):
            print("Flownex project file not found: " + projectPath)
            return
        flownexPath = self.GetFlownexDirectory()
        if flownexPath is not None:
            self.ProjectFile = projectPath
            import IPS
            from IPS import Core
            IPS.Core.FlownexSEDotNet.InitialiseAssemblyResolver(flownexPath)
            ProjectRootPath = projectPath[:-len('.proj')] + '_project' + os.sep
            RunningInstances = IPS.Core.FlownexSEDotNet.GetRunningFlownexInstances()
            
            if RunningInstances:
                for runningFSE in RunningInstances:
                    if runningFSE.Project is not None and \
                            os.path.normpath(runningFSE.Project.ProjectRootPath) == os.path.normpath(ProjectRootPath):
                        self.AttachedProject = runningFSE.Project
                        self.FlownexSE = runningFSE
                        self.SimulationController = IPS.Core.SimulationControlHelper(self.AttachedProject.SimulationControlHelper)
                        self.NetworkBuilder = IPS.Core.NetworkBuilder(self.AttachedProject.Builder)
                        break
            if self.AttachedProject is None:  # Flownex project is not open so start a new instance and open project
                self.FlownexSE = IPS.Core.FlownexSEDotNet.LaunchFlownexSE()
                self.FlownexSE.OpenProject(projectPath,'','')
                self.AttachedProject = self.FlownexSE.Project
                if self.AttachedProject is None:
                    print(f"Failed to load project: {projectPath}")
                self.SimulationController = IPS.Core.SimulationControlHelper(self.AttachedProject.SimulationControlHelper)
                self.NetworkBuilder = IPS.Core.NetworkBuilder(self.AttachedProject.Builder)
            return self.AttachedProject
        else:
            print("Flownex not registered for API use")
            print("Run registercomapi.bat as Administrator from the Flownex install directory to rectify this")
        
    def IsFnxAvailable(self):
        return self.FlownexInstallationDetected
    
    def LaunchFlownexIfNeeded(self, projectPath: str):
        self.AttachToProject(projectPath)
        return self.AttachedProject is not None
    
    def CloseProject(self):
        if self.FlownexSE is not None:
            try:
                self.FlownexSE.CloseProject()            
            except Exception as e:
                print(f"Error closing Flownex project: {e}")
        self.AttachedProject = None
        self.SimulationController = None
        self.NetworkBuilder = None
        self.ProjectFile = ""
        self._property_cache.clear()


    def ExitApplication(self):
        if self.FlownexSE is not None:
            self.CloseProject()
            self.FlownexSE.Exit()

        
    def SetPropertyValueUnit(self, componentIdentifier: str, propertyIdentifier: str, value: float, unitTxt: str):
        if self.AttachedProject is None or self.SimulationController is None or self.NetworkBuilder is None:
            return        
        try:
            valueWithUnit = str(value) + " " + unitTxt if unitTxt != "" else str(value)
            _cachedProperty = self._GetCachedProperty(componentIdentifier, propertyIdentifier)
            if _cachedProperty is None:
                print(f"Error setting property value: " + componentIdentifier + "." + propertyIdentifier)
                return
            _cachedProperty.SetValueFromString(valueWithUnit)
        except Exception as e:
            print(f"Error setting property value: {e} :" + componentIdentifier + "." + propertyIdentifier)

    def GetPropertyValueUnit(self, componentIdentifier: str, propertyIdentifier: str, IOFile_unitTxt: str) -> Optional[float]:
        if self.AttachedProject is None or self.SimulationController is None or self.NetworkBuilder is None:
            return None
        try:
            _cachedProperty = self._GetCachedProperty(componentIdentifier, propertyIdentifier)
            if _cachedProperty is None:
                print(f"Error getting property value: " + componentIdentifier + "." + propertyIdentifier)
                return
            valueStr = _cachedProperty.GetValueAsString()

            if valueStr is not None:
                #detect unit
                numericValue = 0.0
                splitted = valueStr.split()
                #test if three sections (value, unit group, and unit)     
                try:           
                    numericValue = float(splitted[0])   
                    if len(splitted) >= 3:
                        m_pUnitGroup = UnitGroup.GetUnitGroupFromIdentifierName(splitted[1])
                        if m_pUnitGroup is None:
                            print(f"Error parsing property value: unknown unit group " + splitted[1] + " :" + componentIdentifier + "." + propertyIdentifier)
                            return None
                        #assemble the full unit name from the rest of the splitted sections, in case a unit name contains a space
                        API_UnitName = ' '.join(splitted[2:])
                        API_Unit = m_pUnitGroup.UnitFromName(API_UnitName)
                        if API_Unit is not None:
                            UserUnit = m_pUnitGroup.UnitFromName(IOFile_unitTxt)
                            if UserUnit is None:
                                print(f"Unknown user unit in IO File" + IOFile_unitTxt + " :" + componentIdentifier + "." + propertyIdentifier)
                                return None
                            numericValue = UnitGroup.Convert(numericValue, API_Unit, UserUnit)                        
                        else:
                            print(f"Error parsing property value: unknown unit " + API_UnitName + " :" + componentIdentifier + "." + propertyIdentifier)
                            return None
                    return numericValue        
                except Exception as e:
                    print(f"Error parsing property value: {e} :" + componentIdentifier + "." + propertyIdentifier)
                    return None   
                
            else:
                print(f"Error getting property value: no value returned for " + componentIdentifier + "." + propertyIdentifier)
        except Exception as e:
            print(f"Error getting property value: {e} :" + componentIdentifier + "." + propertyIdentifier)
        return None       

    #for general properties that do not need units 
    def SetPropertyValue(self, componentIdentifier: str, propertyIdentifier: str, value: str):
        if self.AttachedProject is None or self.SimulationController is None or self.NetworkBuilder is None:
            return
        try:           
            _cachedProperty = self._GetCachedProperty(componentIdentifier, propertyIdentifier)
            if _cachedProperty is None:
                print(f"Error setting property value: " + componentIdentifier + "." + propertyIdentifier)
                return
            _cachedProperty.SetValueFromString(value)           
        except Exception as e:
            print(f"Error setting property value: {e} :" + componentIdentifier + "." + propertyIdentifier)


    def GetPropertyValue(self, componentIdentifier: str, propertyIdentifier: str) -> Optional[str]:
        if self.AttachedProject is None or self.SimulationController is None or self.NetworkBuilder is None:
            return None
        try:
            _cachedProperty = self._GetCachedProperty(componentIdentifier, propertyIdentifier)
            if _cachedProperty is None:
                print(f"Error getting property value: " + componentIdentifier + "." + propertyIdentifier)
                return
            valueStr = _cachedProperty.GetValueAsString()
            if valueStr is not None:
                value = valueStr.split()[0]                
                return value
        except Exception as e:
            print(f"Error getting property value: {e} :" + componentIdentifier + "." + propertyIdentifier)
        return None
    
    #this function will block unitl Flownex has completed the simulation, or timeout (in ms) is reached
    #other non blocking APIs is available for fire and poll for completion. See Flownex API documentation
    def RunSteadyStateSimulationBlocking(self):
        if self.AttachedProject is None or self.SimulationController is None or self.NetworkBuilder is None:
            return False
        try:
            success = self.SimulationController.SolveSteadyStateAndWaitToComplete(120000)          
            return success
        except Exception as e:
            print(f"Error running steady state simulation: {e}")
        return False
    
    def StartTransientSimulation(self):
        if self.AttachedProject is None or self.SimulationController is None or self.NetworkBuilder is None:
            return False
        try:
            self.AttachedProject.ResetTime()
            self.AttachedProject.RunSimulation()
            return True
        except Exception as e:
            print(f"Error starting transient simulation: {e}")
        return False
    
    def StopTransientSimulation(self):
        if self.AttachedProject is None or self.SimulationController is None or self.NetworkBuilder is None:
            return False
        try:
            self.AttachedProject.DeactivateSimulation()
            return True
        except Exception as e:
            print(f"Error stopping transient simulation: {e}")
        return False
    
    #self._property_cache: Dict[str, Any] = {}
    def _GetCachedProperty(self, componentIdentifier: str, propertyIdentifier: str):
        key = componentIdentifier + "." + propertyIdentifier
        if key in self._property_cache:
            return self._property_cache[key]
        else:
            import IPS
            from IPS import Core
            Element = IPS.Core.Element(self.AttachedProject.GetElement(componentIdentifier))
            if Element is None:
                print(f"Error getting property value: unknown component " + componentIdentifier)
                return None
            Property = IPS.Core.Property(Element.GetPropertyFromFullDisplayName(propertyIdentifier))
            if Property is None:
                print(f"Error getting property value: unknown property " + propertyIdentifier + " in component " + componentIdentifier)
                return None
            self._property_cache[key] = Property
            return Property
