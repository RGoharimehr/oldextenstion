"""
Base classes for SimReady component simulation system
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Optional


class BaseUnit:
    """
    Represents the dimensional exponents of a unit (L, M, T, I, Θ, N, J, plane angle).
    """
    __slots__ = (
        "m_sText",
        "L", "M", "T", "I", "Th", "N", "J", "Ang"
    )

    def __init__(
        self,
        sText: str,
        dLength_m_Exponent: float,
        dMass_kg_Exponent: float,
        dTime_s_Exponent: float,
        dElectric_current_A_Exponent: float,
        dTemperature_K_Exponent: float,
        dAmount_of_substance_mol_Exponent: float,
        dLuminous_intensity_cd_Exponent: float,
        dPlane_angle_rad_Exponent: float
    ):
        self.m_sText = sText
        self.L = dLength_m_Exponent
        self.M = dMass_kg_Exponent
        self.T = dTime_s_Exponent
        self.I = dElectric_current_A_Exponent
        self.Th = dTemperature_K_Exponent
        self.N = dAmount_of_substance_mol_Exponent
        self.J = dLuminous_intensity_cd_Exponent
        self.Ang = dPlane_angle_rad_Exponent

    @property
    def sText(self) -> str:
        return self.m_sText

    def _combine(self, other: BaseUnit, op) -> BaseUnit:
        return BaseUnit(
            f"{self.sText}{op}{other.sText}",
            self.L + other.L,
            self.M + other.M,
            self.T + other.T,
            self.I + other.I,
            self.Th + other.Th,
            self.N + other.N,
            self.J + other.J,
            self.Ang + other.Ang
        )

    def __mul__(self, other: BaseUnit) -> BaseUnit:
        return self._combine(other, "*")

    def __truediv__(self, other: BaseUnit) -> BaseUnit:
        return BaseUnit(
            f"{self.sText}/{other.sText}",
            self.L - other.L,
            self.M - other.M,
            self.T - other.T,
            self.I - other.I,
            self.Th - other.Th,
            self.N - other.N,
            self.J - other.J,
            self.Ang - other.Ang
        )

    def __xor__(self, power: int) -> BaseUnit:
        return BaseUnit(
            f"{self.sText}^{power}" if self.sText else "",
            self.L * power,
            self.M * power,
            self.T * power,
            self.I * power,
            self.Th * power,
            self.N * power,
            self.J * power,
            self.Ang * power
        )

    @staticmethod
    def one_over(rhs: BaseUnit) -> BaseUnit:
        return BaseUnit(
            f"1/{rhs.sText}" if rhs.sText else "",
            -rhs.L, -rhs.M, -rhs.T, -rhs.I, -rhs.Th, -rhs.N, -rhs.J, -rhs.Ang
        )

    @staticmethod
    def sqrt(rhs: BaseUnit) -> BaseUnit:
        return BaseUnit(
            f"sqrt({rhs.sText})" if rhs.sText else "",
            rhs.L / 2, rhs.M / 2, rhs.T / 2, rhs.I / 2,
            rhs.Th / 2, rhs.N / 2, rhs.J / 2, rhs.Ang / 2
        )

    def __repr__(self):
        return f"BaseUnit({self.sText})"


# BaseUnit static fields
BaseUnit.none = BaseUnit("", 0, 0, 0, 0, 0, 0, 0, 0)
BaseUnit.one = BaseUnit("", 0, 0, 0, 0, 0, 0, 0, 0)
BaseUnit.length = BaseUnit("length", 1, 0, 0, 0, 0, 0, 0, 0)
BaseUnit.mass = BaseUnit("mass", 0, 1, 0, 0, 0, 0, 0, 0)
BaseUnit.time = BaseUnit("time", 0, 0, 1, 0, 0, 0, 0, 0)
BaseUnit.electric_current = BaseUnit("electric_current", 0, 0, 0, 1, 0, 0, 0, 0)
BaseUnit.temperature = BaseUnit("temperature", 0, 0, 0, 0, 1, 0, 0, 0)
BaseUnit.amount_of_substance = BaseUnit("amount_of_substance", 0, 0, 0, 0, 0, 1, 0, 0)
BaseUnit.luminous_intensity = BaseUnit("luminous_intensity", 0, 0, 0, 0, 0, 0, 1, 0)
BaseUnit.derived_plane_angle = BaseUnit("derived_plane_angle", 0, 0, 0, 0, 0, 0, 0, 1)

# Derived base units
BaseUnit.derived_area = BaseUnit.length * BaseUnit.length
BaseUnit.derived_volume = BaseUnit.length * BaseUnit.length * BaseUnit.length
BaseUnit.derived_force = BaseUnit.length * BaseUnit.mass / (BaseUnit.time ^ 2)
BaseUnit.derived_frequency = BaseUnit.one / BaseUnit.time
BaseUnit.derived_pressure = BaseUnit.derived_force / BaseUnit.derived_area
BaseUnit.derived_dynamic_viscosity = BaseUnit.derived_pressure * BaseUnit.time
BaseUnit.derived_work = (BaseUnit.length ^ 2) * BaseUnit.mass / (BaseUnit.time ^ 2)
BaseUnit.derived_power = (BaseUnit.length ^ 2) * BaseUnit.mass / (BaseUnit.time ^ 3)
BaseUnit.derived_electrical_potential = BaseUnit.derived_power / BaseUnit.electric_current
BaseUnit.derived_electrical_resistance = BaseUnit.derived_electrical_potential / BaseUnit.electric_current
BaseUnit.derived_electrical_conductance = BaseUnit.electric_current / BaseUnit.derived_electrical_potential
BaseUnit.derived_electrical_charge = BaseUnit.time * BaseUnit.electric_current
BaseUnit.derived_electrical_capacitance = BaseUnit.derived_electrical_charge / BaseUnit.derived_electrical_potential
BaseUnit.derived_magnetic_flux = BaseUnit.derived_electrical_potential * BaseUnit.time
BaseUnit.derived_inductance = BaseUnit.derived_magnetic_flux / BaseUnit.electric_current
BaseUnit.derived_angular_velocity = BaseUnit.derived_plane_angle / BaseUnit.time
BaseUnit.derived_angular_acceleration = BaseUnit.derived_angular_velocity / BaseUnit.time


class Unit:
    """
    Mirrors the C# Unit class with operator overloading.
    """
    __slots__ = (
        "m_sText", "m_dScale", "m_dOffset",
        "m_bBuiltInUnit", "m_pBaseUnit", "m_pCustomUnitOffset"
    )

    def __init__(
        self,
        sText: str,
        dScale: float,
        dOffset: float,
        pBaseUnit: Optional[BaseUnit],
        bBuiltInUnit: bool = False
    ):
        self.m_sText = sText
        self.m_dScale = dScale
        self.m_dOffset = dOffset
        self.m_bBuiltInUnit = bBuiltInUnit
        self.m_pBaseUnit = pBaseUnit

    @property
    def sText(self) -> str:
        return self.m_sText

    @property
    def dScale(self) -> float:
        return self.m_dScale

    @property
    def dOffset(self) -> float:
        return self.m_dOffset

    @property
    def bBuiltInUnit(self) -> bool:
        return self.m_bBuiltInUnit

    @property
    def pBaseUnit(self) -> Optional[BaseUnit]:
        return self.m_pBaseUnit

    def ConvertToSI(self, value: float) -> float:
       #if self.m_pCustomUnitOffset is None: # variable atmospheric pressure not supported outside of flownex
        return value * self.m_dScale + self.m_dOffset
       # return (value * self.m_dScale + self.m_dOffset) + self.m_pCustomUnitOffset.GetOffSetInSI()

    def ConvertFromSI(self, value: float) -> float:
     #   if self.m_pCustomUnitOffset is None: # variable atmospheric pressure not supported outside of flownex
        return (value - self.m_dOffset) / self.m_dScale
      #  return ((value - self.m_pCustomUnitOffset.GetOffSetInSI()) - self.m_dOffset) / self.m_dScale

    @property
    def SaveValueAsSI(self) -> bool:
        return self.m_pCustomUnitOffset is not None

    def __mul__(self, other: Unit) -> Unit:
        return Unit(
            f"{self.m_sText}.{other.m_sText}",
            self.m_dScale * other.m_dScale,
            self.m_dOffset + other.m_dOffset,
            self._combine_base_mul(other),
            self.m_bBuiltInUnit or other.m_bBuiltInUnit
        )

    def _combine_base_mul(self, other: Unit) -> Optional[BaseUnit]:
        if self.m_pBaseUnit and other.m_pBaseUnit:
            return self.m_pBaseUnit * other.m_pBaseUnit
        return None

    def __truediv__(self, other: Unit) -> Unit:
        return Unit(
            f"{self.m_sText}/{other.m_sText}",
            self.m_dScale / other.m_dScale,
            self.m_dOffset,
            self._combine_base_div(other),
            self.m_bBuiltInUnit or other.m_bBuiltInUnit
        )

    def _combine_base_div(self, other: Unit) -> Optional[BaseUnit]:
        if self.m_pBaseUnit and other.m_pBaseUnit:
            return self.m_pBaseUnit / other.m_pBaseUnit
        return None

    def __xor__(self, power: int) -> Unit:
        if power == 2:
            txt = self.m_sText + "²"
        elif power == 3:
            txt = self.m_sText + "³"
        else:
            txt = f"{self.m_sText}^{power}"
        return Unit(
            txt,
            self.m_dScale ** power,
            self.m_dOffset ** 1,  # no special offset handling (same as original approach)
            self.m_pBaseUnit ^ power if self.m_pBaseUnit else None,
            self.m_bBuiltInUnit
        )

    @staticmethod
    def one_over(rhs: Unit) -> Unit:
        return Unit(
            f"1/{rhs.m_sText}",
            1 / rhs.m_dScale,
            0.0,
            BaseUnit.one_over(rhs.m_pBaseUnit) if rhs.m_pBaseUnit else None,
            True or rhs.m_bBuiltInUnit
        )

    @staticmethod
    def sqrt(rhs: Unit) -> Unit:
        return Unit(
            f"sqrt({rhs.m_sText})",
            math.sqrt(rhs.m_dScale),
            rhs.m_dOffset,
            BaseUnit.sqrt(rhs.m_pBaseUnit) if rhs.m_pBaseUnit else None,
            rhs.m_bBuiltInUnit
        )

    def __str__(self):
        return self.m_sText

    def __repr__(self):
        return f"Unit({self.m_sText}, scale={self.m_dScale}, offset={self.m_dOffset})"


# Helper free functions for symmetry with original usage
def one_over(u: Unit) -> Unit:
    return Unit.one_over(u)


def sqrt(u: Unit) -> Unit:
    return Unit.sqrt(u)


# Static unit definitions (order respects dependencies)
Unit.none = Unit("", 1.0, 0.0, BaseUnit.none, True)
Unit.one = Unit("1", 1.0, 0.0, BaseUnit.one, True)

# Angle
Unit.rad = Unit("rad", 1.0, 0.0, BaseUnit.derived_plane_angle, True)
Unit.deg = Unit("°", math.pi / 180.0, 0.0, BaseUnit.derived_plane_angle, True)

# Time
Unit.ms = Unit("ms", 0.001, 0.0, BaseUnit.time, True)
Unit.s = Unit("s", 1.0, 0.0, BaseUnit.time, True)
Unit.min = Unit("min", 60.0, 0.0, BaseUnit.time, True)
Unit.h = Unit("h", 3600.0, 0.0, BaseUnit.time, True)
Unit.day = Unit("day", 86400.0, 0.0, BaseUnit.time, True)
Unit.yr = Unit("yr", 31536000.0, 0.0, BaseUnit.time, True)

# Mass
Unit.kg = Unit("kg", 1.0, 0.0, BaseUnit.mass, True)
Unit.g = Unit("g", 0.001, 0.0, BaseUnit.mass, True)
Unit.mg = Unit("mg", 0.000001, 0.0, BaseUnit.mass, True)
Unit.ton = Unit("ton", 1000.0, 0.0, BaseUnit.mass, True)
Unit.lbm = Unit("lbm", 0.453592, 0.0, BaseUnit.mass, True)
Unit.klbm = Unit("klbm", 0.453592 * 1000, 0.0, BaseUnit.mass, True)
Unit.grain = Unit("grain", 0.0000648, 0.0, BaseUnit.mass, True)
Unit.oz_avdp = Unit("oz (avdp)", 0.02835, 0.0, BaseUnit.mass, True)
Unit.ton_US = Unit("ton (U.S.)", 907.18474, 0.0, BaseUnit.mass, True)
Unit.ton_SI = Unit("ton (SI)", 1000.0, 0.0, BaseUnit.mass, True)
Unit.slug = Unit("slug", 14.59, 0.0, BaseUnit.mass, True)

# Length
Unit.m = Unit("m", 1.0, 0.0, BaseUnit.length, True)
Unit.cm = Unit("cm", 0.01, 0.0, BaseUnit.length, True)
Unit.µm = Unit("µm", 1e-6, 0.0, BaseUnit.length, True)
Unit.mm = Unit("mm", 0.001, 0.0, BaseUnit.length, True)
Unit.km = Unit("km", 1000.0, 0.0, BaseUnit.length, True)
Unit.Å = Unit("Å", 1e-10, 0.0, BaseUnit.length, True)
Unit.ft = Unit("ft", 0.3048, 0.0, BaseUnit.length, True)
Unit.inch = Unit("in", 0.0254, 0.0, BaseUnit.length, True)
Unit.yd = Unit("yd", 3 * Unit.ft.dScale, 0.0, BaseUnit.length, True)
Unit.mi = Unit("mi", 1609.3, 0.0, BaseUnit.length, True)
Unit.mils = Unit("mils", 0.0254 / 1000.0, 0.0, BaseUnit.length, True)

# Force
Unit.N = Unit("N", 1.0, 0.0, BaseUnit.derived_force, True)
Unit.kN = Unit("kN", 1000.0, 0.0, BaseUnit.derived_force, True)
Unit.dyn = Unit("dyn", 1e-5, 0.0, BaseUnit.derived_force, True)

# Convenience composites (respecting previously defined units)
Unit.kg_m_over_s2 = Unit.kg * Unit.m / (Unit.s ^ 2)
Unit.kg_force = Unit("kg_force", 9.8067, 0.0, BaseUnit.derived_force, True)
Unit.g_force = Unit("g_force", 0.009807, 0.0, BaseUnit.derived_force, True)
Unit.pdl = Unit("pdl", 0.1383, 0.0, BaseUnit.derived_force, True)
Unit.lbf = Unit("lbf", 4.448, 0.0, BaseUnit.derived_force, True)
Unit.kip = Unit("kip", 4448, 0.0, BaseUnit.derived_force, True)
Unit.ton_force = Unit("ton_force", 8896, 0.0, BaseUnit.derived_force, True)

# Frequency
Unit.Hz = Unit("Hz", 1.0, 0.0, BaseUnit.derived_frequency, True)
Unit.one_over_s = Unit("1/s", 1.0, 0.0, BaseUnit.derived_frequency, True)
Unit.kHz = Unit("kHz", 1000.0, 0.0, BaseUnit.derived_frequency, True)
Unit.MHz = Unit("MHz", 1_000_000.0, 0.0, BaseUnit.derived_frequency, True)

# Pressure (Henry's constant etc.)
Unit.N_over_m2 = Unit.N / (Unit.m ^ 2)
Unit.atm = Unit("atm", 101326, 0.0, BaseUnit.derived_force / (BaseUnit.length ^ 2), True)
Unit.mmHg = Unit("mmHg", 133.3, 0.0, BaseUnit.derived_force / (BaseUnit.length ^ 2), True)
Unit.lbf_over_in2 = Unit.lbf / (Unit.inch ^ 2)
Unit.lbf_over_ft2 = Unit.lbf / (Unit.ft ^ 2)

# Power
Unit.kW = Unit("kW", 1000.0, 0.0, BaseUnit.derived_power, True)
Unit.MW = Unit("MW", 1_000_000.0, 0.0, BaseUnit.derived_power, True)
Unit.GW = Unit("GW", 1_000_000_000.0, 0.0, BaseUnit.derived_power, True)
Unit.hp = Unit("hp", 745.8, 0.0, BaseUnit.derived_power, True)

# Energy
Unit.J = Unit("J", 1.0, 0.0, BaseUnit.derived_work, True)
Unit.kJ = Unit("kJ", 1000.0, 0.0, BaseUnit.derived_work, True)
Unit.MJ = Unit("MJ", 1_000_000.0, 0.0, BaseUnit.derived_work, True)
Unit.GJ = Unit("GJ", 1_000_000_000.0, 0.0, BaseUnit.derived_work, True)
Unit.kWh = Unit.kW * Unit.h
Unit.MWh = Unit.MW * Unit.h
Unit.cal = Unit("cal", 4.187, 0.0, BaseUnit.derived_work, True)
Unit.kcal = Unit("kcal", 1000.0 * Unit.cal.dScale, 0.0, BaseUnit.derived_work, True)
Unit.erg = Unit("erg", 1e-7, 0.0, BaseUnit.derived_work, True)
Unit.ft_lbf = Unit.ft * Unit.lbf
Unit.Btu = Unit("Btu", 1055, 0.0, BaseUnit.derived_work, True)
Unit.ft_pdl = Unit.ft * Unit.pdl
Unit.hp_h = Unit.hp * Unit.h
Unit.therm = Unit("therm", 105_500_000, 0.0, BaseUnit.derived_work, True)
Unit.in_lbf = Unit.inch * Unit.lbf
Unit.hp_min = Unit.hp * Unit.min
Unit.hp_s = Unit.hp * Unit.s
Unit.eV = Unit("eV", 1.60207E-19, 0.0, BaseUnit.derived_work, True)

# Electrical power forms
Unit.W = Unit("W", 1.0, 0.0, BaseUnit.derived_power, True)
Unit.VA = Unit("VA", 1.0, 0.0, BaseUnit.derived_power, True)
Unit.VAr = Unit("VAr", 1.0, 0.0, BaseUnit.derived_power, True)
Unit.kVA = Unit("kVA", 1000.0, 0.0, BaseUnit.derived_power, True)
Unit.kVAr = Unit("kVAr", 1000.0, 0.0, BaseUnit.derived_power, True)
Unit.MVA = Unit("MVA", 1_000_000.0, 0.0, BaseUnit.derived_power, True)
Unit.MVAr = Unit("MVAr", 1_000_000.0, 0.0, BaseUnit.derived_power, True)

# Rate forms
Unit.cal_over_s = Unit.cal / Unit.s
Unit.kcal_over_s = Unit.kcal / Unit.s
Unit.erg_over_s = Unit.erg / Unit.s
Unit.ft_lbf_over_s = Unit.ft_lbf / Unit.s
Unit.Btu_over_h = Unit.Btu / Unit.h
Unit.Btu_over_s = Unit.Btu / Unit.s
Unit.ft_pdl_over_s = Unit.ft_pdl / Unit.s
Unit.in_lbf_over_s = Unit.in_lbf / Unit.s
Unit.ton_refrigeration = Unit("ton refrigeration", 745.8, 0.0, BaseUnit.derived_power, True)
Unit.Btu_over_min = Unit.Btu / Unit.min

# Substance quantity
Unit.mol = Unit("mol", 1.0, 0.0, BaseUnit.amount_of_substance, True)
Unit.kmol = Unit("kmol", 1000.0, 0.0, BaseUnit.amount_of_substance, True)

# Temperature
Unit.K = Unit("K", 1.0, 0.0, BaseUnit.temperature, True)
Unit.deg_R = Unit("°R", 5.0 / 9.0, 0.0, BaseUnit.temperature, True)
Unit.deg_F = Unit("°F", 5.0 / 9.0, 459.67 * 5.0 / 9.0, BaseUnit.temperature, True)
Unit.deg_C = Unit("°C", 1.0, 273.15, BaseUnit.temperature, True)

# Differential temperature
Unit.Delta_K = Unit("K", 1.0, 0.0, BaseUnit.temperature, True)
Unit.Delta_deg_R = Unit("°R", 5.0 / 9.0, 0.0, BaseUnit.temperature, True)
Unit.Delta_deg_F = Unit("°F", 5.0 / 9.0, 0.0, BaseUnit.temperature, True)
Unit.Delta_deg_C = Unit("°C", 1.0, 0.0, BaseUnit.temperature, True)

# Volume
Unit.m3 = (Unit.m ^ 3)
Unit.cm3 = (Unit.cm ^ 3)
Unit.l = Unit("l", 0.001, 0.0, BaseUnit.derived_volume, True)
Unit.kl = Unit("kl", 1.0, 0.0, BaseUnit.derived_volume, True)
Unit.Ml = Unit("Ml", 1000.0, 0.0, BaseUnit.derived_volume, True)
Unit.Gl = Unit("Gl", 1_000_000.0, 0.0, BaseUnit.derived_volume, True)
Unit.µm3 = (Unit.µm ^ 3)
Unit.ft3 = (Unit.ft ^ 3)
Unit.in3 = (Unit.inch ^ 3)
Unit.gal_US = Unit("gal (U.S.)", 0.003785, 0.0, BaseUnit.derived_volume, True)

# Current
Unit.A = Unit("A", 1.0, 0.0, BaseUnit.electric_current, True)
Unit.kA = Unit("kA", 1000.0, 0.0, BaseUnit.electric_current, True)
Unit.MA = Unit("MA", 1_000_000.0, 0.0, BaseUnit.electric_current, True)
Unit.abampere = Unit("abampere", 10.0, 0.0, BaseUnit.electric_current, True)
Unit.statampere = Unit("statampere", 0.00000000033356, 0.0, BaseUnit.electric_current, True)

# Voltage
Unit.V = Unit("V", 1.0, 0.0, BaseUnit.derived_electrical_potential, True)
Unit.kV = Unit("kV", 1000.0, 0.0, BaseUnit.derived_electrical_potential, True)
Unit.MV = Unit("MV", 1_000_000.0, 0.0, BaseUnit.derived_electrical_potential, True)
Unit.kg_m2_over_A_s3 = Unit.kg * (Unit.m ^ 2) / (Unit.A * (Unit.s ^ 3))
Unit.W_over_A = Unit.W / Unit.A
Unit.abvolt = Unit("abvolt", 1e-8, 0.0, BaseUnit.derived_electrical_potential, True)
Unit.statvolt = Unit("statvolt", 299.8, 0.0, BaseUnit.derived_electrical_potential, True)

# Resistance
Unit.Ohm = Unit("Ohm", 1.0, 0.0, BaseUnit.derived_electrical_resistance, True)
Unit.mOhm = Unit("mOhm", 1.0 / 1000.0, 0.0, BaseUnit.derived_electrical_resistance, True)
Unit.kOhm = Unit("kOhm", 1000.0, 0.0, BaseUnit.derived_electrical_resistance, True)
Unit.MOhm = Unit("MOhm", 1_000_000.0, 0.0, BaseUnit.derived_electrical_resistance, True)
Unit.kg_m2_over_A2_s3 = Unit.kg * (Unit.m ^ 2) / ((Unit.A ^ 2) * (Unit.s ^ 3))
Unit.V_over_A = Unit.V / Unit.A
Unit.abohm = Unit("abohm", 1e-9, 0.0, BaseUnit.derived_electrical_resistance, True)
Unit.statohm = Unit("statohm", 898800000000, 0.0, BaseUnit.derived_electrical_resistance, True)

# Admittance
Unit.Siemens = Unit("S", 1.0, 0.0, BaseUnit.derived_electrical_conductance, True)

# Per Unit
Unit.pu = Unit("pu", 1.0, 0.0, BaseUnit.none, True)

# Angular acceleration
Unit.rad_over_s2 = Unit.rad / (Unit.s ^ 2)
Unit.rad_over_min2 = Unit.rad / (Unit.min ^ 2)
Unit.rad_over_h2 = Unit.rad / (Unit.h ^ 2)
Unit.rev_over_min2 = Unit("rev/min²", 2.0 * math.pi / (Unit.min.dScale * Unit.min.dScale), 0.0, BaseUnit.derived_angular_acceleration, True)

# Acceleration
Unit.m_over_s2 = Unit.m / (Unit.s ^ 2)
Unit.cm_over_s2 = Unit.cm / (Unit.s ^ 2)
Unit.m_over_h2 = Unit.m / (Unit.h ^ 2)
Unit.ft_over_s2 = Unit.ft / (Unit.s ^ 2)
Unit.ft_over_min2 = Unit.ft / (Unit.min ^ 2)
Unit.ft_over_h2 = Unit.ft / (Unit.h ^ 2)

# Acceleration reciprocal
Unit.one_over_m_over_s2 = one_over(Unit.m_over_s2)
Unit.one_over_cm_over_s2 = one_over(Unit.cm / (Unit.s ^ 2))
Unit.one_over_m_over_h2 = one_over(Unit.m / (Unit.h ^ 2))
Unit.one_over_ft_over_s2 = one_over(Unit.ft / (Unit.s ^ 2))
Unit.one_over_ft_over_min2 = one_over(Unit.ft / (Unit.min ^ 2))
Unit.one_over_ft_over_h2 = one_over(Unit.ft / (Unit.h ^ 2))

# Area
Unit.m2 = (Unit.m ^ 2)
Unit.mm2 = (Unit.mm ^ 2)
Unit.cm2 = (Unit.cm ^ 2)
Unit.µm2 = (Unit.µm ^ 2)
Unit.ha = Unit("ha", 10000, 0.0, BaseUnit.derived_area, True)
Unit.km2 = (Unit.km ^ 2)
Unit.ft2 = (Unit.ft ^ 2)
Unit.in2 = (Unit.inch ^ 2)
Unit.yd2 = (Unit.yd ^ 2)
Unit.acre = Unit("acre", 4047.0, 0.0, BaseUnit.derived_area, True)
Unit.mi2 = (Unit.mi ^ 2)

# Heat transfer helper examples
Unit.W_over_K = Unit.W / Unit.K
Unit.W_over_deg_C = Unit.W / Unit.deg_C
Unit.kW_over_K = Unit.kW / Unit.K
Unit.kW_over_deg_C = Unit.kW / Unit.deg_C
Unit.MW_over_K = Unit.MW / Unit.K
Unit.MW_over_deg_C = Unit.MW / Unit.deg_C
Unit.GW_over_K = Unit.GW / Unit.K
Unit.GW_over_deg_C = Unit.GW / Unit.deg_C
Unit.BTU_over_hr_deg_F = Unit.Btu / (Unit.h * Unit.deg_F)

# Density
Unit.kg_over_m3 = Unit.kg / (Unit.m ^ 3)
Unit.g_over_m3 = Unit.g / (Unit.m ^ 3)
Unit.mg_over_m3 = Unit.mg / (Unit.m ^ 3)
Unit.mg_over_l = Unit.mg / Unit.l
Unit.g_over_cm3 = Unit.g / (Unit.cm ^ 3)
Unit.lbm_over_ft3 = Unit.lbm / (Unit.ft ^ 3)
Unit.lbm_over_gal = Unit.lbm / Unit.gal_US
Unit.lbm_over_in3 = Unit.lbm / (Unit.inch ^ 3)
Unit.grain_over_ft3 = Unit.grain / (Unit.ft ^ 3)

# Diffusion Coefficient
Unit.m2_over_s = (Unit.m ^ 2) / Unit.s
Unit.cm2_over_s = (Unit.cm ^ 2) / Unit.s
Unit.m2_over_h = (Unit.m ^ 2) / Unit.h
Unit.ft2_over_s = (Unit.ft ^ 2) / Unit.s
Unit.ft2_over_h = (Unit.ft ^ 2) / Unit.h

# Efficiency
Unit.zero_one = Unit("0-1", 1.0, 0.0, BaseUnit.none, True)
Unit.percentage = Unit("%", 1.0 / 100.0, 0.0, BaseUnit.none, True)

# Electrical Capacitance
Unit.F = Unit("F", 1.0, 0.0, BaseUnit.derived_electrical_capacitance, True)
Unit.A2_s4_over_kg_m2 = (Unit.A ^ 2) * (Unit.s ^ 4) / (Unit.kg * (Unit.m ^ 2))
Unit.A_s_over_V = Unit.A * Unit.s / Unit.V
Unit.abfarad = Unit("abfarad", 1_000_000_000, 0.0, BaseUnit.derived_electrical_capacitance, True)
Unit.statfarad = Unit("statfarad", 1.113e-12, 0.0, BaseUnit.derived_electrical_capacitance, True)

# Electrical Charge
Unit.C = Unit("C", 1.0, 0.0, BaseUnit.derived_electrical_charge, True)
Unit.A_s = Unit.A * Unit.s
Unit.abcoulomb = Unit("abcoulomb", 10.0, 0.0, BaseUnit.derived_electrical_charge, True)
Unit.statcoulomb = Unit("statcoulomb", 3.336e-10, 0.0, BaseUnit.derived_electrical_charge, True)

# Electrical Field Strength
Unit.V_over_m = Unit.V / Unit.m
Unit.kg_m_over_A_s3 = Unit.kg * Unit.m / (Unit.A * (Unit.s ^ 3))
Unit.V_over_cm = Unit.V / Unit.cm
Unit.abvolt_over_m = Unit.abvolt / Unit.m
Unit.statvolt_over_m = Unit.statvolt / Unit.m
Unit.V_over_in = Unit.V / Unit.inch

# Electrical Resistivity
Unit.ohm_m = Unit.Ohm * Unit.m
Unit.kg_m5_over_A2_s3 = Unit.kg * (Unit.m ^ 5) / ((Unit.A ^ 2) * (Unit.s ^ 3))
Unit.abohm_m = Unit.abohm * Unit.m
Unit.statohm_m = Unit.statohm * Unit.m

# Energy Density
Unit.J_over_m3 = Unit.J / (Unit.m ^ 3)
Unit.kWh_over_m3 = Unit.kWh / (Unit.m ^ 3)
Unit.cal_over_cm3 = Unit.cal / (Unit.cm ^ 3)
Unit.kcal_over_cm3 = Unit.kcal / (Unit.cm ^ 3)
Unit.erg_over_cm3 = Unit.erg / (Unit.cm ^ 3)
Unit.ft_lbf_over_ft3 = Unit.ft * Unit.lbf / (Unit.ft ^ 3)
Unit.Btu_over_ft3 = Unit.Btu / (Unit.ft ^ 3)
Unit.kWh_over_ft3 = Unit.kWh / (Unit.ft ^ 3)
Unit.hp_h_over_ft3 = Unit.hp * Unit.h / (Unit.ft ^ 3)
Unit.kJ_over_m3 = Unit.kJ / Unit.m3
Unit.MJ_over_m3 = Unit.MJ / Unit.m3
Unit.GJ_over_m3 = Unit.GJ / Unit.m3

# Energy per Area
Unit.J_over_m2 = Unit.J / (Unit.m ^ 2)
Unit.cal_over_cm2 = Unit.cal / (Unit.cm ^ 2)
Unit.kcal_over_cm2 = Unit.kcal / (Unit.cm ^ 2)
Unit.erg_over_cm2 = Unit.erg / (Unit.cm ^ 2)
Unit.ft_lbf_over_ft2 = Unit.ft * Unit.lbf / (Unit.ft ^ 2)
Unit.Btu_over_ft2 = Unit.Btu / (Unit.ft ^ 2)
Unit.hp_h_over_ft2 = Unit.hp * Unit.h / (Unit.ft ^ 2)
Unit.kWh_over_ft2 = Unit.kWh / (Unit.ft ^ 2)
Unit.kJ_over_m2 = Unit.kJ / (Unit.m ^ 2)
Unit.MJ_over_m2 = Unit.MJ / (Unit.m ^ 2)

# Energy, Linear
Unit.J_over_m = Unit.J / Unit.m
Unit.cal_over_cm = Unit.cal / Unit.cm
Unit.kcal_over_cm = Unit.kcal / Unit.cm
Unit.erg_over_cm = Unit.erg / Unit.cm
Unit.ft_lbf_over_ft = Unit.ft * Unit.lbf / Unit.ft
Unit.Btu_over_ft = Unit.Btu / Unit.ft
Unit.hp_h_over_ft = Unit.hp * Unit.h / Unit.ft
Unit.kWh_over_ft = Unit.kWh / Unit.ft
Unit.kJ_over_m = Unit.kJ / Unit.m

# Flow Rate, Mass/Force
Unit.kg_over_N_s = Unit.kg / (Unit.N * Unit.s)
Unit.g_over_cm2_atm_s = Unit.g / ((Unit.cm ^ 2) * Unit.atm * Unit.s)
Unit.lbm_over_ft2_atm_h = Unit.lbm / ((Unit.ft ^ 2) * Unit.atm * Unit.h)

# Flow Rate, Mass/Volume
Unit.kg_over_m3_s = Unit.kg / ((Unit.m ^ 3) * Unit.s)
Unit.g_over_cm3_s = Unit.g / ((Unit.cm ^ 3) * Unit.s)
Unit.g_over_cm3_min = Unit.g / ((Unit.cm ^ 3) * Unit.min)
Unit.g_over_cm3_h = Unit.g / ((Unit.cm ^ 3) * Unit.h)
Unit.lbm_over_ft3_s = Unit.lbm / ((Unit.ft ^ 3) * Unit.s)
Unit.lbm_over_ft3_min = Unit.lbm / ((Unit.ft ^ 3) * Unit.min)
Unit.lbm_over_ft3_h = Unit.lbm / ((Unit.ft ^ 3) * Unit.h)

# Flow Rate, Mass
Unit.kg_over_s = Unit.kg / Unit.s
Unit.g_over_s = Unit.g / Unit.s
Unit.kg_over_h = Unit.kg / Unit.h
Unit.ton_SI_over_h = Unit.ton_SI / Unit.h
Unit.ton_SI_over_min = Unit.ton_SI / Unit.min
Unit.ton_SI_over_s = Unit.ton_SI / Unit.s
Unit.ton_US_over_h = Unit.ton_US / Unit.h
Unit.ton_US_over_min = Unit.ton_US / Unit.min
Unit.ton_US_over_s = Unit.ton_US / Unit.s
Unit.lbm_over_s = Unit.lbm / Unit.s
Unit.lbm_over_min = Unit.lbm / Unit.min
Unit.lbm_over_h = Unit.lbm / Unit.h
Unit.klbm_over_h = Unit.klbm / Unit.h

# Flow Rate, Volume
Unit.m3_over_s = (Unit.m ^ 3) / Unit.s
Unit.m3_over_min = (Unit.m ^ 3) / Unit.min
Unit.m3_over_h = (Unit.m ^ 3) / Unit.h
Unit.cm3_over_s = (Unit.cm ^ 3) / Unit.s
Unit.cfs = (Unit.ft ^ 3) / Unit.s
Unit.in3_over_s = (Unit.inch ^ 3) / Unit.s
Unit.cfm = (Unit.ft ^ 3) / Unit.min
Unit.cfh = (Unit.ft ^ 3) / Unit.h
Unit.gal_over_s = Unit.gal_US / Unit.s
Unit.gpm = Unit.gal_US / Unit.min
Unit.gph = Unit.gal_US / Unit.h
Unit.lps = Unit.l / Unit.s
Unit.lpm = Unit.l / Unit.min
Unit.lph = Unit.l / Unit.h
Unit.klps = Unit.kl / Unit.s
Unit.klpm = Unit.kl / Unit.min
Unit.klph = Unit.kl / Unit.h
Unit.Mlpm = Unit.Ml / Unit.min
Unit.Mlph = Unit.Ml / Unit.h
Unit.Glph = Unit.Gl / Unit.h

# Flux, Mass
Unit.kg_over_m2_s = Unit.kg / ((Unit.m ^ 2) * Unit.s)
Unit.g_over_cm2_s = Unit.g / ((Unit.cm ^ 2) * Unit.s)
Unit.g_over_m2_min = Unit.g / ((Unit.m ^ 2) * Unit.min)
Unit.g_over_m2_h = Unit.g / ((Unit.m ^ 2) * Unit.h)
Unit.lbm_over_ft2_s = Unit.lbm / ((Unit.ft ^ 2) * Unit.s)
Unit.lbm_over_ft2_min = Unit.lbm / ((Unit.ft ^ 2) * Unit.min)
Unit.lbm_over_ft2_h = Unit.lbm / ((Unit.ft ^ 2) * Unit.h)

# Force per Mass
Unit.N_over_kg = Unit.N / Unit.kg
Unit.dyn_over_g = Unit.dyn / Unit.g
Unit.kg_f_over_kg = Unit.kg_force / Unit.kg
Unit.lbf_over_lbm = Unit.lbf / Unit.lbm
Unit.lbf_over_slug = Unit.lbf / Unit.slug

# Force, Body
Unit.N_over_m3 = Unit.N / (Unit.m ^ 3)
Unit.dyn_over_cm3 = Unit.dyn / (Unit.cm ^ 3)
Unit.kg_f_over_cm3 = Unit.kg_force / (Unit.cm ^ 3)
Unit.lbf_over_ft3 = Unit.lbf / (Unit.ft ^ 3)
Unit.lbf_over_in3 = Unit.lbf / (Unit.inch ^ 3)
Unit.ton_f_over_ft3 = Unit.ton_force / (Unit.ft ^ 3)

# Force per Velocity
Unit.N_s_over_m = Unit.N * Unit.s / Unit.m
Unit.kg_f_s_over_m = Unit.kg_force * Unit.s / Unit.m
Unit.lbf_min_over_ft = Unit.lbf * Unit.min / Unit.ft

# Heat Transfer Coefficient (already partly defined earlier, adding if missing)
Unit.W_over_m2_K = Unit.W / ((Unit.m ^ 2) * Unit.K)
Unit.cal_over_s_cm2_deg_C = Unit.cal / (Unit.s * (Unit.cm ^ 2) * Unit.deg_C)
Unit.kcal_over_h_m2_deg_C = Unit.kcal / (Unit.h * (Unit.m ^ 2) * Unit.deg_C)
Unit.erg_over_s_cm2_deg_C = Unit.erg / (Unit.s * (Unit.cm ^ 2) * Unit.deg_C)
Unit.Btu_over_h_ft2_deg_F = Unit.Btu / (Unit.h * (Unit.ft ^ 2) * Unit.deg_F)
Unit.kcal_over_h_ft2_deg_C = Unit.kcal / (Unit.h * (Unit.ft ^ 2) * Unit.deg_C)
Unit.kW_over_m2_K = Unit.kW / ((Unit.m ^ 2) * Unit.K)

# Inductance
Unit.H = Unit("H", 1.0, 0.0, BaseUnit.derived_inductance, True)
Unit.kg_m2_over_A2_s2 = Unit.kg * (Unit.m ^ 2) / ((Unit.A ^ 2) * (Unit.s ^ 2))
Unit.V_s_over_A = Unit.V * Unit.s / Unit.A
Unit.abhenry = Unit("abhenry", 1e-9, 0.0, BaseUnit.derived_inductance, True)
Unit.stathenry = Unit("stathenry", 898800000000, 0.0, BaseUnit.derived_inductance, True)

# Magnetic Flux
Unit.Wb = Unit("Wb", 1.0, 0.0, BaseUnit.derived_magnetic_flux, True)
Unit.kg_m2_over_A_s2 = Unit.kg * (Unit.m ^ 2) / (Unit.A * (Unit.s ^ 2))
Unit.V_s = Unit.V * Unit.s

# Mass per Area
Unit.kg_over_m2 = Unit.kg / (Unit.m ^ 2)
Unit.g_over_cm2 = Unit.g / (Unit.cm ^ 2)
Unit.lbm_over_ft2 = Unit.lbm / (Unit.ft ^ 2)
Unit.lbm_over_in2 = Unit.lbm / (Unit.inch ^ 2)
Unit.ton_over_mi2 = Unit.ton_US / (Unit.mi ^ 2)

# Molar Flow
Unit.mol_over_s = Unit.mol / Unit.s

# Molar Mass
Unit.g_over_mol = Unit.g / Unit.mol
Unit.kg_over_mol = Unit.kg / Unit.mol
Unit.lbm_over_mol = Unit.lbm / Unit.mol
Unit.kg_over_kmol = Unit.kg / Unit.kmol
Unit.lbm_over_kmol = Unit.lbm / Unit.kmol

# Moment Inertia, Area
Unit.m4 = (Unit.m ^ 4)
Unit.cm4 = (Unit.cm ^ 4)
Unit.in4 = (Unit.inch ^ 4)
Unit.ft4 = (Unit.ft ^ 4)

# Moment Inertia, Mass
Unit.kg_m2 = Unit.kg * (Unit.m ^ 2)
Unit.g_cm2 = Unit.g * (Unit.cm ^ 2)
Unit.lbm_ft2 = Unit.lbm * (Unit.ft ^ 2)
Unit.lbf_ft_s2 = Unit.lbf * Unit.ft * (Unit.s ^ 2)
Unit.lbm_in2 = Unit.lbm * (Unit.inch ^ 2)
Unit.lbf_in_over_s = Unit.lbf * Unit.inch / Unit.s

# Momentum Flow Rate
# (kg*m/s^2) form already implicit; keeping only listed composites
Unit.g_cm_over_s2 = Unit.g * Unit.cm / (Unit.s ^ 2)
Unit.lbm_ft_over_s2 = Unit.lbm * Unit.ft / (Unit.s ^ 2)
Unit.lbm_ft_over_min2 = Unit.lbm * Unit.ft / (Unit.min ^ 2)

# Momentum, Angular
Unit.kg_m2_over_s = Unit.kg * (Unit.m ^ 2) / Unit.s
Unit.g_cm2_over_s = Unit.g * (Unit.cm ^ 2) / Unit.s
Unit.lbm_ft2_over_s = Unit.lbm * (Unit.ft ^ 2) / Unit.s
Unit.lbm_ft2_over_min = Unit.lbm * (Unit.ft ^ 2) / Unit.min

# Momentum (linear)
Unit.kg_m_over_s = Unit.kg * Unit.m / Unit.s
Unit.g_cm_over_s = Unit.g * Unit.cm / Unit.s
Unit.lbm_ft_over_s = Unit.lbm * Unit.ft / Unit.s
Unit.lbm_ft_over_min = Unit.lbm * Unit.ft / Unit.min

# Power Density (volumetric)
Unit.W_over_m3 = Unit.W / (Unit.m ^ 3)
Unit.kW_over_m3 = Unit.kW / (Unit.m ^ 3)
Unit.cal_over_s_cm3 = Unit.cal / (Unit.s * (Unit.cm ^ 3))
Unit.kcal_over_s_cm3 = Unit.kcal / (Unit.s * (Unit.cm ^ 3))
Unit.erg_over_s_cm3 = Unit.erg / (Unit.s * (Unit.cm ^ 3))
Unit.ft_lbf_over_s_ft3 = Unit.ft * Unit.lbf / (Unit.s * (Unit.ft ^ 3))
Unit.Btu_over_s_ft3 = Unit.Btu / (Unit.s * (Unit.ft ^ 3))
Unit.Btu_over_h_ft3 = Unit.Btu / (Unit.h * (Unit.ft ^ 3))
Unit.kW_over_ft3 = Unit.kW / (Unit.ft ^ 3)
Unit.hp_over_ft3 = Unit.hp / (Unit.ft ^ 3)

# Power Flux (area)
Unit.W_over_m2 = Unit.W / (Unit.m ^ 2)
Unit.kW_over_m2 = Unit.kW / (Unit.m ^ 2)
Unit.cal_over_s_cm2 = Unit.cal / (Unit.s * (Unit.cm ^ 2))
Unit.kcal_over_s_cm2 = Unit.kcal / (Unit.s * (Unit.cm ^ 2))
Unit.erg_over_s_cm2 = Unit.erg / (Unit.s * (Unit.cm ^ 2))
Unit.ft_lbf_over_s_ft2 = Unit.ft * Unit.lbf / (Unit.s * (Unit.ft ^ 2))
Unit.Btu_over_s_ft2 = Unit.Btu / (Unit.s * (Unit.ft ^ 2))
Unit.Btu_over_h_ft2 = Unit.Btu / (Unit.h * (Unit.ft ^ 2))
Unit.hp_over_ft2 = Unit.hp / (Unit.ft ^ 2)
Unit.kW_over_ft2 = Unit.kW / (Unit.ft ^ 2)

# Power, Linear
Unit.W_over_m = Unit.W / Unit.m
Unit.kW_over_m = Unit.kW / Unit.m
Unit.cal_over_s_cm = Unit.cal / (Unit.s * Unit.cm)
Unit.kcal_over_s_cm = Unit.kcal / (Unit.s * Unit.cm)
Unit.erg_over_s_cm = Unit.erg / (Unit.s * Unit.cm)
Unit.ft_lbf_over_s_ft = Unit.ft * Unit.lbf / (Unit.s * Unit.ft)
Unit.Btu_over_s_ft = Unit.Btu / (Unit.s * Unit.ft)
Unit.Btu_over_h_ft = Unit.Btu / (Unit.h * Unit.ft)
Unit.hp_over_ft = Unit.hp / Unit.ft


# Pressure, Stress
Unit.Pa = Unit("Pa", 1.0, 0.0, BaseUnit.derived_pressure, True)
Unit.kPa = Unit("kPa", 1000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.MPa = Unit("MPa", 1_000_000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.GPa = Unit("GPa", 1_000_000_000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.mPa = Unit("mPa", 0.001, 0.0, BaseUnit.derived_pressure, True)
Unit.Pa_gauge = Unit("Pa(g)", 1.0, 0.0, BaseUnit.derived_pressure, True)
Unit.kPa_gauge = Unit("kPa(g)", 1000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.MPa_gauge = Unit("MPa(g)", 1_000_000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.psi = Unit("psi", Unit.lbf.dScale / (Unit.inch.dScale * Unit.inch.dScale), 0.0, BaseUnit.derived_pressure, True)
Unit.psi_gauge = Unit("psi(g)", Unit.lbf.dScale / (Unit.inch.dScale * Unit.inch.dScale), 0.0, BaseUnit.derived_pressure, True)
Unit.dyn_over_cm2 = Unit.dyn / (Unit.cm ^ 2)
Unit.kg_f_over_cm2 = Unit.kg_force / (Unit.cm ^ 2)
Unit.kg_f_over_m2 = Unit.kg_force / (Unit.m ^ 2)
Unit.bar = Unit("bar", 100000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.mbar = Unit("mbar", 100.0, 0.0, BaseUnit.derived_pressure, True)
Unit.bar_gauge = Unit("bar(g)", 100000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.mbar_gauge = Unit("mbar(g)", 100.0, 0.0, BaseUnit.derived_pressure, True)
Unit.in_H2O_gauge = Unit("in H2O(g)", 249.1, 0.0, BaseUnit.derived_pressure, True)
Unit.std_atm = Unit("std. atm", 101330.0, 0.0, BaseUnit.derived_pressure, True)
Unit.pdl_over_ft2 = Unit.pdl / (Unit.ft ^ 2)
Unit.ton_f_over_in2 = Unit.ton_force / (Unit.inch ^ 2)
Unit.m_H2O = Unit("m H2O", 9806.65, 0.0, BaseUnit.derived_pressure, True)
Unit.cm_H2O = Unit("cm H2O", 98.0665, 0.0, BaseUnit.derived_pressure, True)
Unit.mm_H2O = Unit("mm H2O", 9.80665, 0.0, BaseUnit.derived_pressure, True)
Unit.in_H2O = Unit("in H2O", 249.1, 0.0, BaseUnit.derived_pressure, True)
Unit.ft_H2O = Unit("ft H2O", 2989.0, 0.0, BaseUnit.derived_pressure, True)
Unit.mm_Hg = Unit("mm Hg", 133.3, 0.0, BaseUnit.derived_pressure, True)
Unit.in_Hg = Unit("in Hg", 3386.3, 0.0, BaseUnit.derived_pressure, True)
Unit.N_over_mm2 = Unit.N / (Unit.mm ^ 2)
Unit.lb_over_in2 = Unit.lbf / (Unit.inch ^ 2)

# Differential Pressure, Stress
Unit.Delta_Pa = Unit("Pa", 1.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_kPa = Unit("kPa", 1000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_MPa = Unit("MPa", 1_000_000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_GPa = Unit("GPa", 1_000_000_000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_mPa = Unit("mPa", 0.001, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_Pa_gauge = Unit("Pa(g)", 1.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_kPa_gauge = Unit("kPa(g)", 1000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_MPa_gauge = Unit("MPa(g)", 1_000_000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_psi = Unit("psi", Unit.lbf.dScale / (Unit.inch.dScale * Unit.inch.dScale), 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_psi_gauge = Unit("psi(g)", Unit.lbf.dScale / (Unit.inch.dScale * Unit.inch.dScale), 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_dyn_over_cm2 = Unit.dyn / (Unit.cm ^ 2)
Unit.Delta_kg_f_over_cm2 = Unit.kg_force / (Unit.cm ^ 2)
Unit.Delta_kg_f_over_m2 = Unit.kg_force / (Unit.m ^ 2)
Unit.Delta_bar = Unit("bar", 100000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_mbar = Unit("mbar", 100.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_bar_gauge = Unit("bar(g)", 100000.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_mbar_gauge = Unit("mbar(g)", 100.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_std_atm = Unit("std. atm", 101330.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_pdl_over_ft2 = Unit.pdl / (Unit.ft ^ 2)
Unit.Delta_ton_f_over_in2 = Unit.ton_force / (Unit.inch ^ 2)
Unit.Delta_m_H2O = Unit("m H2O", 9806.65, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_cm_H2O = Unit("cm H2O", 98.0665, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_mm_H2O = Unit("mm H2O", 9.80665, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_in_H2O = Unit("in H2O", 249.1, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_in_H2O_gauge = Unit("in H2O(g)", 249.1, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_ft_H2O = Unit("ft H2O", 2989.0, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_mm_Hg = Unit("mm Hg", 133.3, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_in_Hg = Unit("in Hg", 3386.3, 0.0, BaseUnit.derived_pressure, True)
Unit.Delta_N_over_mm2 = Unit.N / (Unit.mm ^ 2)
Unit.Delta_lb_over_in2 = Unit.lbf / (Unit.inch ^ 2)

# Specific Energy (subset shown)
Unit.J_over_kg = Unit.J / Unit.kg
Unit.kJ_over_kg = Unit.kJ / Unit.kg
Unit.MJ_over_kg = Unit.MJ / Unit.kg
Unit.m2_over_s2 = (Unit.m ^ 2) / (Unit.s ^ 2)
Unit.cal_over_g = Unit.cal / Unit.g
Unit.kcal_over_g = Unit.kcal / Unit.g
Unit.ft_lbf_over_lbm = Unit.ft * Unit.lbf / Unit.lbm
Unit.btu_over_lbm = Unit.Btu / Unit.lbm
Unit.hp_h_over_lbm = Unit.hp * Unit.h / Unit.lbm
Unit.kWh_over_lbm = Unit.kWh / Unit.lbm
Unit.GJ_over_kg = Unit.GJ / Unit.kg


# Specific Energy molar
Unit.J_over_mol = Unit.J / Unit.mol
Unit.kJ_over_kmol = Unit.kJ / Unit.kmol
Unit.kJ_over_mol = Unit.kJ / Unit.mol
Unit.MJ_over_kmol = Unit.MJ / Unit.kmol

# Specific Heat / Gas Constant
Unit.J_over_kg_K = Unit.J / (Unit.kg * Unit.K)
Unit.J_over_kg_deg_C = Unit.J / (Unit.kg * Unit.deg_C)
Unit.kJ_over_kg_K = Unit.kJ / (Unit.kg * Unit.K)
Unit.kJ_over_kg_deg_C = Unit.kJ / (Unit.kg * Unit.deg_C)
Unit.MJ_over_kg_K = Unit.MJ / (Unit.kg * Unit.K)
Unit.MJ_over_kg_deg_C = Unit.MJ / (Unit.kg * Unit.deg_C)
Unit.m2_over_s2_K = (Unit.m ^ 2) / ((Unit.s ^ 2) * Unit.K)
Unit.cal_over_g_K = Unit.cal / (Unit.g * Unit.K)
Unit.erg_over_g_K = Unit.erg / (Unit.g * Unit.K)
Unit.Btu_over_lbm_deg_R = Unit.Btu / (Unit.lbm * Unit.deg_R)
Unit.ft_lbf_over_lbm_deg_R = Unit.ft * Unit.lbf / (Unit.lbm * Unit.deg_R)

# Specific Surface
Unit.m2_over_kg = (Unit.m ^ 2) / Unit.kg
Unit.cm2_over_g = (Unit.cm ^ 2) / Unit.g
Unit.µm2_over_lbm = (Unit.µm ^ 2) / Unit.lbm
Unit.ft2_over_lbm = (Unit.ft ^ 2) / Unit.lbm
Unit.m3_over_kg = (Unit.m ^ 3) / Unit.kg
Unit.cm3_over_g = (Unit.cm ^ 3) / Unit.g
Unit.µm3_over_g = (Unit.µm ^ 3) / Unit.g
Unit.ft3_over_lbm = (Unit.ft ^ 3) / Unit.lbm

# Surface Tension
Unit.N_over_m = Unit.N / Unit.m
Unit.dyn_over_cm = Unit.dyn / Unit.cm
Unit.lbf_over_ft = Unit.lbf / Unit.ft
Unit.lbf_over_in = Unit.lbf / Unit.inch

# Thermal Capacitance
Unit.J_over_K = Unit.J / Unit.K
Unit.kJ_over_K = Unit.kJ / Unit.K
Unit.MJ_over_K = Unit.MJ / Unit.K
Unit.GJ_over_K = Unit.MJ / Unit.K   # matches original (possible intended GJ)
Unit.BTU_over_deg_F = Unit.Btu / Unit.deg_F

# Thermal Conductivity
Unit.W_over_m_K = Unit.W / (Unit.m * Unit.K)
Unit.kW_over_m_K = Unit.kW / (Unit.m * Unit.K)
Unit.cal_over_s_cm_deg_C = Unit.cal / (Unit.s * Unit.cm * Unit.deg_C)
Unit.kcal_over_h_m_deg_C = Unit.kcal / (Unit.h * Unit.m * Unit.deg_C)
Unit.erg_over_s_cm_deg_C = Unit.erg / (Unit.s * Unit.cm * Unit.deg_C)
Unit.Btu_over_h_ft_deg_F = Unit.Btu / (Unit.h * Unit.ft * Unit.deg_F)
Unit.Btu_in_over_h_ft2_deg_F = Unit.Btu * Unit.inch / (Unit.h * (Unit.ft ^ 2) * Unit.deg_F)
Unit.ft_lbf_over_h_ft_deg_F = Unit.ft * Unit.lbf / (Unit.h * Unit.ft * Unit.deg_F)

# Torque
Unit.N_m = Unit.N * Unit.m
Unit.dyn_cm = Unit.dyn * Unit.cm
Unit.lbf_ft = Unit.lbf * Unit.ft
Unit.pdl_ft = Unit.pdl * Unit.ft
Unit.kg_f_ft = Unit.kg_force * Unit.ft

# Corrected mass flow
Unit.kg_over_s_sqrt_K_over_bar = Unit.kg / Unit.s * sqrt(Unit.K) / Unit.bar
Unit.kg_over_s_sqrt_K_over_kPa = Unit.kg / Unit.s * sqrt(Unit.K) / Unit.kPa
Unit.kg_over_s_sqrt_K_over_Pa = Unit.kg / Unit.s * sqrt(Unit.K) / Unit.Pa

# Turbine loss coefficient
Unit.one_over_m4 = one_over(Unit.m ^ 4)
Unit.one_over_ft4 = one_over(Unit.ft ^ 4)
Unit.one_over_in4 = one_over(Unit.inch ^ 4)


# Velocity, Angular:
Unit.rad_over_s = Unit.rad / Unit.s
Unit.rad_over_min = Unit.rad / Unit.min
Unit.rad_over_h = Unit.rad / Unit.h
Unit.rev_over_min = Unit("rev/min", 2 * math.pi / 60, 0.0, BaseUnit.derived_angular_velocity, True)
Unit.rpm = Unit("rpm", 2 * math.pi / 60, 0.0, BaseUnit.derived_angular_velocity, True)
Unit.rps = Unit("rps", 2 * math.pi, 0.0, BaseUnit.derived_angular_velocity, True)

# Velocity:
Unit.mm_over_s = Unit.mm / Unit.s
Unit.m_over_s = Unit.m / Unit.s
Unit.cm_over_s = Unit.cm / Unit.s
Unit.m_over_h = Unit.m / Unit.h
Unit.km_over_h = Unit.km / Unit.h
Unit.in_over_s = Unit.inch / Unit.s
Unit.ft_over_s = Unit.ft / Unit.s
Unit.ft_over_min = Unit.ft / Unit.min
Unit.mi_over_h = Unit.mi / Unit.h

# Viscosity, Dynamic:
Unit.kg_over_m_s = Unit.kg / (Unit.m * Unit.s)
Unit.N_s_over_m2 = Unit.N * Unit.s / (Unit.m ^ 2)
Unit.P = Unit("P", 0.1, 0.0, BaseUnit.derived_dynamic_viscosity, True)
Unit.cP = Unit("cP", 0.001, 0.0, BaseUnit.derived_dynamic_viscosity, True)
Unit.kg_over_m_h = Unit.kg / (Unit.m * Unit.h)
Unit.lbm_over_ft_s = Unit.lbm / (Unit.ft * Unit.s)
Unit.lbm_over_ft_h = Unit.lbm / (Unit.ft * Unit.h)
Unit.lbf_s_over_ft2 = Unit.lbf * Unit.s / (Unit.ft ^ 2)
Unit.St = Unit("St", 0.0001, 0.0, BaseUnit.derived_dynamic_viscosity, True)
Unit.Pa_s = Unit.Pa * Unit.s
Unit.mPa_s = Unit.mPa * Unit.s

# Volumetric Thermal Capacitance
Unit.J_over_m3_K = Unit.J / ((Unit.m ^ 3) * Unit.K)
Unit.kJ_over_m3_K = Unit.kJ / ((Unit.m ^ 3) * Unit.K)
Unit.MJ_over_m3_K = Unit.MJ / ((Unit.m ^ 3) * Unit.K)
Unit.BTU_over_ft3_deg_F = Unit.Btu / ((Unit.ft ^ 3) * Unit.deg_F)
Unit.GJ_over_m3_K = Unit.MJ / ((Unit.m ^ 3) * Unit.K)  # matches original

# Flow Coefficient
Unit.m3_over_s_sqrt_Pa = (Unit.m ^ 3) / (sqrt(Unit.Pa) * Unit.s)
Unit.m3_over_s_sqrt_Bar = (Unit.m ^ 3) / (sqrt(Unit.bar) * Unit.s)
Unit.m3_over_h_sqrt_Pa = (Unit.m ^ 3) / (sqrt(Unit.Pa) * Unit.h)
Unit.m3_over_h_sqrt_Bar = (Unit.m ^ 3) / (sqrt(Unit.bar) * Unit.h)
Unit.gal_over_min_sqrt_Psi = Unit.gal_US / (Unit.min * sqrt(Unit.psi))
Unit.gal_over_s_sqrt_Psi = Unit.gal_US / (Unit.s * sqrt(Unit.psi))
Unit.m3_over_s_sqrt_Pa_over_msquared = (Unit.m ^ 3) / ((sqrt(Unit.Pa) * Unit.s) * (Unit.m ^ 2))
Unit.m3_over_s_sqrt_Bar_over_msquared = (Unit.m ^ 3) / ((sqrt(Unit.bar) * Unit.s) * (Unit.m ^ 2))
Unit.m3_over_h_sqrt_Pa_over_msquared = (Unit.m ^ 3) / ((sqrt(Unit.Pa) * Unit.h) * (Unit.m ^ 2))
Unit.m3_over_h_sqrt_Bar_over_msquared = (Unit.m ^ 3) / ((sqrt(Unit.bar) * Unit.h) * (Unit.m ^ 2))
Unit.gal_over_min_sqrt_Psi_over_insquared = Unit.gal_US / ((Unit.min * sqrt(Unit.psi)) * (Unit.inch ^ 2))
Unit.gal_over_s_sqrt_Psi_over_insquared = Unit.gal_US / ((Unit.s * sqrt(Unit.psi)) * (Unit.inch ^ 2))

# Thermal expansion
Unit.one_over_K = Unit.one / Unit.K
Unit.one_over_deg_C = Unit.one / Unit.deg_C
Unit.one_over_deg_F = Unit.one / Unit.deg_F

# Thermal Resistance
Unit.m2_K_over_W = ((Unit.m ^ 2) * Unit.Delta_K) / Unit.W
Unit.m2_K_over_kW = ((Unit.m ^ 2) * Unit.Delta_K) / Unit.kW
Unit.h_ft2_deg_F_over_Btu = (Unit.h * (Unit.ft ^ 2) * Unit.Delta_deg_F) / Unit.Btu

# Pressure mass flow gradient
Unit.Pa_s_over_kg = (Unit.Pa * Unit.s) / Unit.kg
Unit.kPa_s_over_kg = (Unit.kPa * Unit.s) / Unit.kg
Unit.psi_s_over_lbm = (Unit.psi * Unit.s) / Unit.lbm

# Atkinson resistance
Unit.kg_over_meter7 = Unit.kg / (Unit.m ^ 7)
Unit.lb_over_inch7 = Unit.lbm / (Unit.inch ^ 7)
Unit.lb_over_feet7 = Unit.lbm / (Unit.ft ^ 7)

# Mass per mass
Unit.g_over_g = Unit.g / Unit.g
Unit.g_over_kg = Unit.g / Unit.kg
Unit.kg_over_g = Unit.kg / Unit.g
Unit.kg_over_kg = Unit.kg / Unit.kg
Unit.g_over_ton = Unit.g / Unit.ton
Unit.kg_over_ton = Unit.kg / Unit.ton
Unit.lb_over_lb = Unit.lbm / Unit.lbm
Unit.lb_over_klb = Unit.lbm / Unit.klbm

# Volume per volume
Unit.m3_over_m3 = Unit.m3 / Unit.m3
Unit.l_over_l = Unit.l / Unit.l
Unit.l_over_m3 = Unit.l / Unit.m3
Unit.ft3_over_ft3 = Unit.ft3 / Unit.ft3
Unit.gal_US_over_gal_US = Unit.gal_US / Unit.gal_US
Unit.gal_US_over_ft3 = Unit.gal_US / Unit.ft3

# Misc (millinile)
Unit.mN = Unit("mN", 0.00001, 0.0, BaseUnit.none, True)


class UnitGroups(Enum):
    Acceleration_Angular = 1
    Acceleration = 2
    Acceleration_Reciprocal = 3
    Admittance = 4
    Angle = 5
    Area = 6
    AtkinsonResistance = 7
    AU = 8
    Corrected_Mass_Flow = 9
    Current = 10
    Density = 11
    Diffusion_Coefficient = 12
    Efficiency = 13
    Electrical_Capacitance = 14
    Electrical_Charge = 15
    Electrical_Field_Strength = 16
    Electrical_Resistivity = 17
    Energy_Density = 18
    Energy_per_Area = 19
    Energy_Linear = 20
    Energy = 21
    Flow_Coefficient = 22
    Flow_Coefficient_Over_DSquared = 23
    Flow_Rate_Mass_over_Force = 24
    Flow_Rate_Mass_over_Volume = 25
    Flow_Rate_Mass = 26
    Flow_Rate_Volume = 27
    Flux_Mass = 28
    Force_per_Mass = 29
    Force_Body = 30
    Force = 31
    Force_per_Velocity = 32
    Frequency = 33
    Heat_Transfer_Coefficient = 34
    Henrys_Constant = 35
    Inductance = 36
    Length = 37
    Magnetic_Flux = 38
    Mass_per_Area = 39
    Mass_Per_Mass = 40
    Mass = 41
    Molar_Energy = 42
    Molar_Flow = 43
    Molar_Mass = 44
    Moment_Inertia_Area = 45
    Moment_Inertia_Mass = 46
    Momentum_Flow_Rate = 47
    Momentum_Angular = 48
    Momentum = 49
    NoneGroup = 50  # 'None' reserved in Python context
    Per_Unit = 51
    Power_Density = 52
    Power_Flux = 53
    Power_Linear = 54
    Power = 55
    Pressure_Stress = 56
    Resistance = 57
    Reactivity = 58
    Specific_Energy = 59
    Specific_Heat_Gas_Constant = 60
    Specific_Surface = 61
    Specific_Volume = 62
    Specific_Weight = 63
    Substance_Quantity = 64
    Surface_Tension = 65
    Temperature = 66
    DifferentialTemperature = 67
    DifferentialPressure_Stress = 68
    Thermal_Capacitance = 69
    Thermal_Conductivity = 70
    Thermal_Expansion = 71
    Thermal_Resistance = 72
    Time = 73
    Torque = 74
    Turbine_Loss_Coefficient = 75
    Velocity_Angular = 76
    Velocity = 77
    Viscosity_Dynamic = 78
    Viscosity_Kinematic = 79
    Voltage_Electrical_Potential = 80
    Volume = 81
    Volume_Per_Volume = 82
    Volumetric_Thermal_Capacitance = 83
    Pressure_Massflow_Gradient = 84


class UnitGroup:
    # Global registries (equivalent to static dictionaries)
    _all_unit_groups: List['UnitGroup'] = []
    _identifier_cache: Dict[str, 'UnitGroup'] = {}
    _display_name_cache: Dict[str, 'UnitGroup'] = {}
    SIUnits: List[Unit] = []

    # Static instances (populated below)
    Acceleration_Angular: 'UnitGroup'
    Acceleration: 'UnitGroup'
    Acceleration_Reciprocal: 'UnitGroup'
    Admittance: 'UnitGroup'
    Angle: 'UnitGroup'
    Area: 'UnitGroup'
    AtkinsonResistance: 'UnitGroup'
    AU: 'UnitGroup'
    Corrected_Mass_Flow: 'UnitGroup'
    Current: 'UnitGroup'
    Density: 'UnitGroup'
    Diffusion_Coefficient: 'UnitGroup'
    Efficiency: 'UnitGroup'
    Electrical_Capacitance: 'UnitGroup'
    Electrical_Charge: 'UnitGroup'
    Electrical_Field_Strength: 'UnitGroup'
    Electrical_Resistivity: 'UnitGroup'
    Energy_Density: 'UnitGroup'
    Energy_per_Area: 'UnitGroup'
    Energy_Linear: 'UnitGroup'
    Energy: 'UnitGroup'
    Flow_Coefficient: 'UnitGroup'
    Flow_Coefficient_Over_DSquared: 'UnitGroup'
    Flow_Rate_Mass_over_Force: 'UnitGroup'
    Flow_Rate_Mass_over_Volume: 'UnitGroup'
    Flow_Rate_Mass: 'UnitGroup'
    Flow_Rate_Volume: 'UnitGroup'
    Flux_Mass: 'UnitGroup'
    Force_per_Mass: 'UnitGroup'
    Force_Body: 'UnitGroup'
    Force: 'UnitGroup'
    Force_per_Velocity: 'UnitGroup'
    Frequency: 'UnitGroup'
    Heat_Transfer_Coefficient: 'UnitGroup'
    Henrys_Constant: 'UnitGroup'
    Inductance: 'UnitGroup'
    Length: 'UnitGroup'
    Magnetic_Flux: 'UnitGroup'
    Mass_per_Area: 'UnitGroup'
    Mass_Per_Mass: 'UnitGroup'
    Mass: 'UnitGroup'
    Molar_Energy: 'UnitGroup'
    Molar_Flow: 'UnitGroup'
    Molar_Mass: 'UnitGroup'
    Moment_Inertia_Area: 'UnitGroup'
    Moment_Inertia_Mass: 'UnitGroup'
    Momentum_Flow_Rate: 'UnitGroup'
    Momentum_Angular: 'UnitGroup'
    Momentum: 'UnitGroup'
    _None: 'UnitGroup'
    Per_Unit: 'UnitGroup'
    Power_Density: 'UnitGroup'
    Power_Flux: 'UnitGroup'
    Power_Linear: 'UnitGroup'
    Power: 'UnitGroup'
    Pressure_Stress: 'UnitGroup'
    Resistance: 'UnitGroup'
    Reactivity: 'UnitGroup'
    Specific_Energy: 'UnitGroup'
    Specific_Heat_Gas_Constant: 'UnitGroup'
    Specific_Surface: 'UnitGroup'
    Specific_Volume: 'UnitGroup'
    Specific_Weight: 'UnitGroup'
    Substance_Quantity: 'UnitGroup'
    Surface_Tension: 'UnitGroup'
    Temperature: 'UnitGroup'
    DifferentialTemperature: 'UnitGroup'
    DifferentialPressure_Stress: 'UnitGroup'
    Thermal_Capacitance: 'UnitGroup'
    Thermal_Conductivity: 'UnitGroup'
    Thermal_Expansion: 'UnitGroup'
    Thermal_Resistance: 'UnitGroup'
    Time: 'UnitGroup'
    Torque: 'UnitGroup'
    Turbine_Loss_Coefficient: 'UnitGroup'
    Velocity_Angular: 'UnitGroup'
    Velocity: 'UnitGroup'
    Viscosity_Dynamic: 'UnitGroup'
    Viscosity_Kinematic: 'UnitGroup'
    Voltage_Electrical_Potential: 'UnitGroup'
    Volume: 'UnitGroup'
    Volume_Per_Volume: 'UnitGroup'
    Volumetric_Thermal_Capacitance: 'UnitGroup'
    AtkinsonResistance: 'UnitGroup'
    Pressure_Massflow_Gradient: 'UnitGroup'

    def __init__(self, display_name: str, identifier: UnitGroups):
        self._display_name = display_name
        self._identifier = identifier
        self._identifier_name = identifier.name
        self._units: List[Unit] = []

        UnitGroup._all_unit_groups.append(self)
        UnitGroup._identifier_cache[self._identifier_name] = self
        UnitGroup._display_name_cache[self._display_name] = self

    @property
    def DisplayName(self) -> str:
        return self._display_name

    @property
    def GroupIdentifierName(self) -> str:
        return self._identifier_name

    @property
    def Units(self) -> List[Unit]:
        return self._units

    @property
    def GroupIdentifier(self) -> UnitGroups:
        return self._identifier

    @staticmethod
    def IsSIUnit(unit: Unit) -> bool:
        return unit in UnitGroup.SIUnits
        

    def GetStrings(self) -> List[str]:
        return [u.sText for u in self._units]

    def UnitFromName(self, unit_text: str) -> Optional[Unit]:
        for u in self._units:
            if u.sText == unit_text:
                return u
        return None  # Matches C# behavior (performance choice)

    def HasUnitWithName(self, unit_text: str) -> bool:
        return any(u.sText == unit_text for u in self._units)

    def __str__(self):
        return self._display_name

    @staticmethod
    def GetUnitGroupFromIdentifier(identifier: UnitGroups) -> Optional['UnitGroup']:
        for g in UnitGroup._all_unit_groups:
            if g._identifier == identifier:
                return g
        return None

    @staticmethod
    def GetUnitGroupFromIdentifierName(name: str) -> Optional['UnitGroup']:
        g = UnitGroup._identifier_cache.get(name)
        if g is None:
            g = UnitGroup._display_name_cache.get(name)
            if g is None:
                return None
        return g

    @staticmethod
    def GetUnitGroupFromDisplayName(name: str) -> Optional['UnitGroup']:
        return UnitGroup._display_name_cache.get(name)

    @staticmethod
    def Convert(value: float, API_Unit: Unit, UserUnit: Unit) -> float:
        if API_Unit is UserUnit:
            return value
        #assume both unis is form the same unit group, no error checking for that now. 

        convertedValue = value    
        #Flownex propery values internally use SI units. Units on display are converted to/from SI as needed on the display level     
        #   therefore the unit conversion only do to and from SI, so we use SI as an intermediate step for conversion here
        #Flownex API does however report the value in the display unit.
        if not UnitGroup.IsSIUnit(API_Unit):
            convertedValue = API_Unit.ConvertToSI(convertedValue)
        if not UnitGroup.IsSIUnit(UserUnit):
            convertedValue = UserUnit.ConvertFromSI(convertedValue)
        return convertedValue
    
# Resource name fallback: mimic IPS_Units.<Name> usage (simple mapping to readable text).
def _res(name: str) -> str:
    return name.replace("_", " ")


# Instantiate UnitGroup objects (mirrors static fields in C#).
UnitGroup.Acceleration_Angular = UnitGroup(_res("Acceleration_Angular"), UnitGroups.Acceleration_Angular)
UnitGroup.Acceleration = UnitGroup(_res("Acceleration"), UnitGroups.Acceleration)
UnitGroup.Acceleration_Reciprocal = UnitGroup(_res("Acceleration_Reciprocal"), UnitGroups.Acceleration_Reciprocal)
UnitGroup.Admittance = UnitGroup(_res("Admittance"), UnitGroups.Admittance)
UnitGroup.Angle = UnitGroup(_res("Angle"), UnitGroups.Angle)
UnitGroup.Area = UnitGroup(_res("Area"), UnitGroups.Area)
UnitGroup.AU = UnitGroup(_res("AU"), UnitGroups.AU)
UnitGroup.AtkinsonResistance = UnitGroup(_res("AtkinsonResistance"), UnitGroups.AtkinsonResistance)
UnitGroup.Corrected_Mass_Flow = UnitGroup(_res("Corrected_Mass_Flow"), UnitGroups.Corrected_Mass_Flow)
UnitGroup.Current = UnitGroup(_res("Current"), UnitGroups.Current)
UnitGroup.Density = UnitGroup(_res("Density"), UnitGroups.Density)
UnitGroup.Diffusion_Coefficient = UnitGroup(_res("Diffusion_Coefficient"), UnitGroups.Diffusion_Coefficient)
UnitGroup.Efficiency = UnitGroup(_res("Efficiency"), UnitGroups.Efficiency)
UnitGroup.Electrical_Capacitance = UnitGroup(_res("Electrical_Capacitance"), UnitGroups.Electrical_Capacitance)
UnitGroup.Electrical_Charge = UnitGroup(_res("Electrical_Charge"), UnitGroups.Electrical_Charge)
UnitGroup.Electrical_Field_Strength = UnitGroup(_res("Electrical_Field_Strength"), UnitGroups.Electrical_Field_Strength)
UnitGroup.Electrical_Resistivity = UnitGroup(_res("Electrical_Resistivity"), UnitGroups.Electrical_Resistivity)
UnitGroup.Energy_Density = UnitGroup(_res("Energy_Density"), UnitGroups.Energy_Density)
UnitGroup.Energy_per_Area = UnitGroup(_res("Energy_per_Area"), UnitGroups.Energy_per_Area)
UnitGroup.Energy_Linear = UnitGroup(_res("Energy_Linear"), UnitGroups.Energy_Linear)
UnitGroup.Energy = UnitGroup(_res("Energy"), UnitGroups.Energy)
UnitGroup.Flow_Coefficient = UnitGroup(_res("Flow_Coefficient"), UnitGroups.Flow_Coefficient)
UnitGroup.Flow_Coefficient_Over_DSquared = UnitGroup(_res("Flow_Coefficient_Over_DSquared"), UnitGroups.Flow_Coefficient_Over_DSquared)
UnitGroup.Flow_Rate_Mass_over_Force = UnitGroup(_res("Flow_Rate_Mass_over_Force"), UnitGroups.Flow_Rate_Mass_over_Force)
UnitGroup.Flow_Rate_Mass_over_Volume = UnitGroup(_res("Flow_Rate_Mass_over_Volume"), UnitGroups.Flow_Rate_Mass_over_Volume)
UnitGroup.Flow_Rate_Mass = UnitGroup(_res("Flow_Rate_Mass"), UnitGroups.Flow_Rate_Mass)
UnitGroup.Flow_Rate_Volume = UnitGroup(_res("Flow_Rate_Volume"), UnitGroups.Flow_Rate_Volume)
UnitGroup.Flux_Mass = UnitGroup(_res("Flux_Mass"), UnitGroups.Flux_Mass)
UnitGroup.Force_per_Mass = UnitGroup(_res("Force_per_Mass"), UnitGroups.Force_per_Mass)
UnitGroup.Force_Body = UnitGroup(_res("Force_Body"), UnitGroups.Force_Body)
UnitGroup.Force = UnitGroup(_res("Force"), UnitGroups.Force)
UnitGroup.Force_per_Velocity = UnitGroup(_res("Force_per_Velocity"), UnitGroups.Force_per_Velocity)
UnitGroup.Frequency = UnitGroup(_res("Frequency"), UnitGroups.Frequency)
UnitGroup.Heat_Transfer_Coefficient = UnitGroup(_res("Heat_Transfer_Coefficient"), UnitGroups.Heat_Transfer_Coefficient)
UnitGroup.Henrys_Constant = UnitGroup(_res("Henrys_Constant"), UnitGroups.Henrys_Constant)
UnitGroup.Inductance = UnitGroup(_res("Inductance"), UnitGroups.Inductance)
UnitGroup.Length = UnitGroup(_res("Length"), UnitGroups.Length)
UnitGroup.Magnetic_Flux = UnitGroup(_res("Magnetic_Flux"), UnitGroups.Magnetic_Flux)
UnitGroup.Mass_per_Area = UnitGroup(_res("Mass_per_Area"), UnitGroups.Mass_per_Area)
UnitGroup.Mass_Per_Mass = UnitGroup(_res("Mass_Per_Mass"), UnitGroups.Mass_Per_Mass)
UnitGroup.Mass = UnitGroup(_res("Mass"), UnitGroups.Mass)
UnitGroup.Molar_Energy = UnitGroup(_res("Molar_Energy"), UnitGroups.Molar_Energy)
UnitGroup.Molar_Flow = UnitGroup(_res("Molar_Flow"), UnitGroups.Molar_Flow)
UnitGroup.Molar_Mass = UnitGroup(_res("Molar_Mass"), UnitGroups.Molar_Mass)
UnitGroup.Moment_Inertia_Area = UnitGroup(_res("Moment_Inertia_Area"), UnitGroups.Moment_Inertia_Area)
UnitGroup.Moment_Inertia_Mass = UnitGroup(_res("Moment_Inertia_Mass"), UnitGroups.Moment_Inertia_Mass)
UnitGroup.Momentum_Flow_Rate = UnitGroup(_res("Momentum_Flow_Rate"), UnitGroups.Momentum_Flow_Rate)
UnitGroup.Momentum_Angular = UnitGroup(_res("Momentum_Angular"), UnitGroups.Momentum_Angular)
UnitGroup.Momentum = UnitGroup(_res("Momentum"), UnitGroups.Momentum)
UnitGroup._None = UnitGroup(_res("None"), UnitGroups.NoneGroup)
UnitGroup.Power_Density = UnitGroup(_res("Power_Density"), UnitGroups.Power_Density)
UnitGroup.Power_Flux = UnitGroup(_res("Power_Flux"), UnitGroups.Power_Flux)
UnitGroup.Power_Linear = UnitGroup(_res("Power_Linear"), UnitGroups.Power_Linear)
UnitGroup.Power = UnitGroup(_res("Power"), UnitGroups.Power)
UnitGroup.Pressure_Stress = UnitGroup(_res("Pressure_Stress"), UnitGroups.Pressure_Stress)
UnitGroup.Resistance = UnitGroup(_res("Resistance"), UnitGroups.Resistance)
UnitGroup.Reactivity = UnitGroup(_res("Reactivity"), UnitGroups.Reactivity)
UnitGroup.Per_Unit = UnitGroup(_res("Per_Unit"), UnitGroups.Per_Unit)
UnitGroup.Specific_Energy = UnitGroup(_res("Specific_Energy"), UnitGroups.Specific_Energy)
UnitGroup.Specific_Heat_Gas_Constant = UnitGroup(_res("Specific_Heat_Gas_Constant"), UnitGroups.Specific_Heat_Gas_Constant)
UnitGroup.Specific_Surface = UnitGroup(_res("Specific_Surface"), UnitGroups.Specific_Surface)
UnitGroup.Specific_Volume = UnitGroup(_res("Specific_Volume"), UnitGroups.Specific_Volume)
UnitGroup.Specific_Weight = UnitGroup(_res("Specific_Weight"), UnitGroups.Specific_Weight)
UnitGroup.Substance_Quantity = UnitGroup(_res("Substance_Quantity"), UnitGroups.Substance_Quantity)
UnitGroup.Surface_Tension = UnitGroup(_res("Surface_Tension"), UnitGroups.Surface_Tension)
UnitGroup.Temperature = UnitGroup(_res("Temperature"), UnitGroups.Temperature)
UnitGroup.DifferentialTemperature = UnitGroup(_res("DifferentialTemperature"), UnitGroups.DifferentialTemperature)
UnitGroup.DifferentialPressure_Stress = UnitGroup(_res("DifferentialPressure_Stress"), UnitGroups.DifferentialPressure_Stress)
UnitGroup.Thermal_Capacitance = UnitGroup(_res("Thermal_Capacitance"), UnitGroups.Thermal_Capacitance)
UnitGroup.Thermal_Conductivity = UnitGroup(_res("Thermal_Conductivity"), UnitGroups.Thermal_Conductivity)
UnitGroup.Thermal_Expansion = UnitGroup(_res("Thermal_Expansion"), UnitGroups.Thermal_Expansion)
UnitGroup.Thermal_Resistance = UnitGroup(_res("Thermal_Resistance"), UnitGroups.Thermal_Resistance)
UnitGroup.Time = UnitGroup(_res("Time"), UnitGroups.Time)
UnitGroup.Torque = UnitGroup(_res("Torque"), UnitGroups.Torque)
UnitGroup.Turbine_Loss_Coefficient = UnitGroup(_res("Turbine_Loss_Coefficient"), UnitGroups.Turbine_Loss_Coefficient)
UnitGroup.Velocity_Angular = UnitGroup(_res("Velocity_Angular"), UnitGroups.Velocity_Angular)
UnitGroup.Velocity = UnitGroup(_res("Velocity"), UnitGroups.Velocity)
UnitGroup.Viscosity_Dynamic = UnitGroup(_res("Viscosity_Dynamic"), UnitGroups.Viscosity_Dynamic)
UnitGroup.Viscosity_Kinematic = UnitGroup(_res("Viscosity_Kinematic"), UnitGroups.Viscosity_Kinematic)
UnitGroup.Voltage_Electrical_Potential = UnitGroup(_res("Voltage_Electrical_Potential"), UnitGroups.Voltage_Electrical_Potential)
UnitGroup.Volume = UnitGroup(_res("Volume"), UnitGroups.Volume)
UnitGroup.Volume_Per_Volume = UnitGroup(_res("Volume_Per_Volume"), UnitGroups.Volume_Per_Volume)
UnitGroup.Volumetric_Thermal_Capacitance = UnitGroup(_res("Volumetric_Thermal_Capacitance"), UnitGroups.Volumetric_Thermal_Capacitance)
UnitGroup.Pressure_Massflow_Gradient = UnitGroup(_res("Pressure_Massflow_Gradient"), UnitGroups.Pressure_Massflow_Gradient)


def _populate_units():
    UnitGroup.Acceleration_Angular.Units.append(Unit.rad_over_s2)
    UnitGroup.Acceleration_Angular.Units.append(Unit.rad_over_min2)
    UnitGroup.Acceleration_Angular.Units.append(Unit.rad_over_h2)
    UnitGroup.Acceleration_Angular.Units.append(Unit.rev_over_min2)

    UnitGroup.Acceleration.Units.append(Unit.m_over_s2)
    UnitGroup.Acceleration.Units.append(Unit.cm_over_s2)
    UnitGroup.Acceleration.Units.append(Unit.m_over_h2)
    UnitGroup.Acceleration.Units.append(Unit.ft_over_s2)
    UnitGroup.Acceleration.Units.append(Unit.ft_over_min2)
    UnitGroup.Acceleration.Units.append(Unit.ft_over_h2)

    UnitGroup.Acceleration_Reciprocal.Units.append(Unit.one_over_m_over_s2)
    UnitGroup.Acceleration_Reciprocal.Units.append(Unit.one_over_cm_over_s2)
    UnitGroup.Acceleration_Reciprocal.Units.append(Unit.one_over_m_over_h2)
    UnitGroup.Acceleration_Reciprocal.Units.append(Unit.one_over_ft_over_s2)
    UnitGroup.Acceleration_Reciprocal.Units.append(Unit.one_over_ft_over_min2)
    UnitGroup.Acceleration_Reciprocal.Units.append(Unit.one_over_ft_over_h2)

    UnitGroup.Angle.Units.append(Unit.rad)
    UnitGroup.Angle.Units.append(Unit.deg)

    UnitGroup.Area.Units.append(Unit.m2)
    UnitGroup.Area.Units.append(Unit.mm2)
    UnitGroup.Area.Units.append(Unit.cm2)
    UnitGroup.Area.Units.append(Unit.µm2)
    UnitGroup.Area.Units.append(Unit.ha)
    UnitGroup.Area.Units.append(Unit.km2)
    UnitGroup.Area.Units.append(Unit.ft2)
    UnitGroup.Area.Units.append(Unit.in2)
    UnitGroup.Area.Units.append(Unit.yd2)
    UnitGroup.Area.Units.append(Unit.acre)
    UnitGroup.Area.Units.append(Unit.mi2)

    UnitGroup.AU.Units.append(Unit.W_over_K)
    UnitGroup.AU.Units.append(Unit.W_over_deg_C)
    UnitGroup.AU.Units.append(Unit.kW_over_K)
    UnitGroup.AU.Units.append(Unit.kW_over_deg_C)
    UnitGroup.AU.Units.append(Unit.MW_over_K)
    UnitGroup.AU.Units.append(Unit.MW_over_deg_C)
    UnitGroup.AU.Units.append(Unit.GW_over_K)
    UnitGroup.AU.Units.append(Unit.GW_over_deg_C)
    UnitGroup.AU.Units.append(Unit.BTU_over_hr_deg_F)

    UnitGroup.Current.Units.append(Unit.A)
    UnitGroup.Current.Units.append(Unit.kA)
    UnitGroup.Current.Units.append(Unit.MA)
    UnitGroup.Current.Units.append(Unit.abampere)
    UnitGroup.Current.Units.append(Unit.statampere)

    UnitGroup.Corrected_Mass_Flow.Units.append(Unit.kg_over_s_sqrt_K_over_kPa)
    UnitGroup.Corrected_Mass_Flow.Units.append(Unit.kg_over_s_sqrt_K_over_Pa)
    UnitGroup.Corrected_Mass_Flow.Units.append(Unit.kg_over_s_sqrt_K_over_bar)

    UnitGroup.Density.Units.append(Unit.kg_over_m3)
    UnitGroup.Density.Units.append(Unit.g_over_m3)
    UnitGroup.Density.Units.append(Unit.g_over_cm3)
    UnitGroup.Density.Units.append(Unit.mg_over_m3)
    UnitGroup.Density.Units.append(Unit.mg_over_l)
    UnitGroup.Density.Units.append(Unit.lbm_over_ft3)
    UnitGroup.Density.Units.append(Unit.lbm_over_gal)
    UnitGroup.Density.Units.append(Unit.lbm_over_in3)
    UnitGroup.Density.Units.append(Unit.grain_over_ft3)

    UnitGroup.Diffusion_Coefficient.Units.append(Unit.m2_over_s)
    UnitGroup.Diffusion_Coefficient.Units.append(Unit.cm2_over_s)
    UnitGroup.Diffusion_Coefficient.Units.append(Unit.m2_over_h)
    UnitGroup.Diffusion_Coefficient.Units.append(Unit.ft2_over_s)
    UnitGroup.Diffusion_Coefficient.Units.append(Unit.ft2_over_h)

    UnitGroup.Efficiency.Units.append(Unit.zero_one)
    UnitGroup.Efficiency.Units.append(Unit.percentage)

    UnitGroup.Electrical_Capacitance.Units.append(Unit.F)
    UnitGroup.Electrical_Capacitance.Units.append(Unit.A2_s4_over_kg_m2)
    UnitGroup.Electrical_Capacitance.Units.append(Unit.A_s_over_V)
    UnitGroup.Electrical_Capacitance.Units.append(Unit.abfarad)
    UnitGroup.Electrical_Capacitance.Units.append(Unit.statfarad)

    UnitGroup.Electrical_Charge.Units.append(Unit.C)
    UnitGroup.Electrical_Charge.Units.append(Unit.A_s)
    UnitGroup.Electrical_Charge.Units.append(Unit.abcoulomb)
    UnitGroup.Electrical_Charge.Units.append(Unit.statcoulomb)

    UnitGroup.Electrical_Field_Strength.Units.append(Unit.V_over_m)
    UnitGroup.Electrical_Field_Strength.Units.append(Unit.kg_m_over_A_s3)
    UnitGroup.Electrical_Field_Strength.Units.append(Unit.V_over_cm)
    UnitGroup.Electrical_Field_Strength.Units.append(Unit.abvolt_over_m)
    UnitGroup.Electrical_Field_Strength.Units.append(Unit.statvolt_over_m)
    UnitGroup.Electrical_Field_Strength.Units.append(Unit.V_over_in)

    UnitGroup.Electrical_Resistivity.Units.append(Unit.ohm_m)
    UnitGroup.Electrical_Resistivity.Units.append(Unit.kg_m5_over_A2_s3)
    UnitGroup.Electrical_Resistivity.Units.append(Unit.abohm_m)
    UnitGroup.Electrical_Resistivity.Units.append(Unit.statohm_m)

    UnitGroup.Energy_Density.Units.append(Unit.J_over_m3)
    UnitGroup.Energy_Density.Units.append(Unit.kWh_over_m3)
    UnitGroup.Energy_Density.Units.append(Unit.cal_over_cm3)
    UnitGroup.Energy_Density.Units.append(Unit.kcal_over_cm3)
    UnitGroup.Energy_Density.Units.append(Unit.erg_over_cm3)
    UnitGroup.Energy_Density.Units.append(Unit.ft_lbf_over_ft3)
    UnitGroup.Energy_Density.Units.append(Unit.Btu_over_ft3)
    UnitGroup.Energy_Density.Units.append(Unit.kWh_over_ft3)
    UnitGroup.Energy_Density.Units.append(Unit.hp_h_over_ft3)
    UnitGroup.Energy_Density.Units.append(Unit.kJ_over_m3)
    UnitGroup.Energy_Density.Units.append(Unit.MJ_over_m3)
    UnitGroup.Energy_Density.Units.append(Unit.GJ_over_m3)

    UnitGroup.Energy_per_Area.Units.append(Unit.J_over_m2)
    UnitGroup.Energy_per_Area.Units.append(Unit.cal_over_cm2)
    UnitGroup.Energy_per_Area.Units.append(Unit.kcal_over_cm2)
    UnitGroup.Energy_per_Area.Units.append(Unit.erg_over_cm2)
    UnitGroup.Energy_per_Area.Units.append(Unit.ft_lbf_over_ft2)
    UnitGroup.Energy_per_Area.Units.append(Unit.Btu_over_ft2)
    UnitGroup.Energy_per_Area.Units.append(Unit.hp_h_over_ft2)
    UnitGroup.Energy_per_Area.Units.append(Unit.kWh_over_ft2)
    UnitGroup.Energy_per_Area.Units.append(Unit.kJ_over_m2)
    UnitGroup.Energy_per_Area.Units.append(Unit.MJ_over_m2)

    UnitGroup.Energy_Linear.Units.append(Unit.J_over_m)
    UnitGroup.Energy_Linear.Units.append(Unit.cal_over_cm)
    UnitGroup.Energy_Linear.Units.append(Unit.kcal_over_cm)
    UnitGroup.Energy_Linear.Units.append(Unit.erg_over_cm)
    UnitGroup.Energy_Linear.Units.append(Unit.ft_lbf_over_ft)
    UnitGroup.Energy_Linear.Units.append(Unit.Btu_over_ft)
    UnitGroup.Energy_Linear.Units.append(Unit.hp_h_over_ft)
    UnitGroup.Energy_Linear.Units.append(Unit.kWh_over_ft)
    UnitGroup.Energy_Linear.Units.append(Unit.kJ_over_m)

    UnitGroup.Energy.Units.append(Unit.J)
    UnitGroup.Energy.Units.append(Unit.kJ)
    UnitGroup.Energy.Units.append(Unit.MJ)
    UnitGroup.Energy.Units.append(Unit.GJ)
    UnitGroup.Energy.Units.append(Unit.kWh)
    UnitGroup.Energy.Units.append(Unit.MWh)
    UnitGroup.Energy.Units.append(Unit.cal)
    UnitGroup.Energy.Units.append(Unit.kcal)
    UnitGroup.Energy.Units.append(Unit.erg)
    UnitGroup.Energy.Units.append(Unit.ft_lbf)
    UnitGroup.Energy.Units.append(Unit.Btu)
    UnitGroup.Energy.Units.append(Unit.ft_pdl)
    UnitGroup.Energy.Units.append(Unit.hp_h)
    UnitGroup.Energy.Units.append(Unit.therm)
    UnitGroup.Energy.Units.append(Unit.in_lbf)
    UnitGroup.Energy.Units.append(Unit.hp_min)
    UnitGroup.Energy.Units.append(Unit.hp_s)
    UnitGroup.Energy.Units.append(Unit.eV)

    UnitGroup.Flow_Coefficient.Units.append(Unit.m3_over_s_sqrt_Pa)
    UnitGroup.Flow_Coefficient.Units.append(Unit.m3_over_s_sqrt_Bar)
    UnitGroup.Flow_Coefficient.Units.append(Unit.m3_over_h_sqrt_Pa)
    UnitGroup.Flow_Coefficient.Units.append(Unit.m3_over_h_sqrt_Bar)
    UnitGroup.Flow_Coefficient.Units.append(Unit.gal_over_min_sqrt_Psi)
    UnitGroup.Flow_Coefficient.Units.append(Unit.gal_over_s_sqrt_Psi)

    UnitGroup.Flow_Coefficient_Over_DSquared.Units.append(Unit.m3_over_s_sqrt_Pa_over_msquared)
    UnitGroup.Flow_Coefficient_Over_DSquared.Units.append(Unit.m3_over_s_sqrt_Bar_over_msquared)
    UnitGroup.Flow_Coefficient_Over_DSquared.Units.append(Unit.m3_over_h_sqrt_Pa_over_msquared)
    UnitGroup.Flow_Coefficient_Over_DSquared.Units.append(Unit.m3_over_h_sqrt_Bar_over_msquared)
    UnitGroup.Flow_Coefficient_Over_DSquared.Units.append(Unit.gal_over_min_sqrt_Psi_over_insquared)
    UnitGroup.Flow_Coefficient_Over_DSquared.Units.append(Unit.gal_over_s_sqrt_Psi_over_insquared)

    UnitGroup.Flow_Rate_Mass_over_Force.Units.append(Unit.kg_over_N_s)
    UnitGroup.Flow_Rate_Mass_over_Force.Units.append(Unit.g_over_cm2_atm_s)
    UnitGroup.Flow_Rate_Mass_over_Force.Units.append(Unit.lbm_over_ft2_atm_h)

    UnitGroup.Flow_Rate_Mass_over_Volume.Units.append(Unit.kg_over_m3_s)
    UnitGroup.Flow_Rate_Mass_over_Volume.Units.append(Unit.g_over_cm3_s)
    UnitGroup.Flow_Rate_Mass_over_Volume.Units.append(Unit.g_over_cm3_min)
    UnitGroup.Flow_Rate_Mass_over_Volume.Units.append(Unit.g_over_cm3_h)
    UnitGroup.Flow_Rate_Mass_over_Volume.Units.append(Unit.lbm_over_ft3_s)
    UnitGroup.Flow_Rate_Mass_over_Volume.Units.append(Unit.lbm_over_ft3_min)
    UnitGroup.Flow_Rate_Mass_over_Volume.Units.append(Unit.lbm_over_ft3_h)

    UnitGroup.Flow_Rate_Mass.Units.append(Unit.kg_over_s)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.g_over_s)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.kg_over_h)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.ton_SI_over_h)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.ton_SI_over_min)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.ton_SI_over_s)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.ton_US_over_h)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.ton_US_over_min)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.ton_US_over_s)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.lbm_over_s)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.lbm_over_min)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.lbm_over_h)
    UnitGroup.Flow_Rate_Mass.Units.append(Unit.klbm_over_h)

    UnitGroup.Flow_Rate_Volume.Units.append(Unit.m3_over_s)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.m3_over_min)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.m3_over_h)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.cm3_over_s)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.cfs)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.in3_over_s)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.cfm)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.cfh)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.gal_over_s)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.lps)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.lpm)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.lph)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.gpm)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.gph)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.klps)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.klpm)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.klph)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.Mlpm)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.Mlph)
    UnitGroup.Flow_Rate_Volume.Units.append(Unit.Glph)

    UnitGroup.Flux_Mass.Units.append(Unit.kg_over_m2_s)
    UnitGroup.Flux_Mass.Units.append(Unit.g_over_cm2_s)
    UnitGroup.Flux_Mass.Units.append(Unit.g_over_m2_min)
    UnitGroup.Flux_Mass.Units.append(Unit.g_over_m2_h)
    UnitGroup.Flux_Mass.Units.append(Unit.lbm_over_ft2_s)
    UnitGroup.Flux_Mass.Units.append(Unit.lbm_over_ft2_min)
    UnitGroup.Flux_Mass.Units.append(Unit.lbm_over_ft2_h)

    UnitGroup.Force_per_Mass.Units.append(Unit.N_over_kg)
    UnitGroup.Force_per_Mass.Units.append(Unit.dyn_over_g)
    UnitGroup.Force_per_Mass.Units.append(Unit.kg_f_over_kg)
    UnitGroup.Force_per_Mass.Units.append(Unit.lbf_over_lbm)
    UnitGroup.Force_per_Mass.Units.append(Unit.lbf_over_slug)

    UnitGroup.Force_Body.Units.append(Unit.N_over_m3)
    UnitGroup.Force_Body.Units.append(Unit.dyn_over_cm3)
    UnitGroup.Force_Body.Units.append(Unit.kg_f_over_cm3)
    UnitGroup.Force_Body.Units.append(Unit.lbf_over_ft3)
    UnitGroup.Force_Body.Units.append(Unit.lbf_over_in3)
    UnitGroup.Force_Body.Units.append(Unit.ton_f_over_ft3)

    UnitGroup.Force.Units.append(Unit.N)
    UnitGroup.Force.Units.append(Unit.kN)
    UnitGroup.Force.Units.append(Unit.dyn)
    UnitGroup.Force.Units.append(Unit.kg_m_over_s2)
    UnitGroup.Force.Units.append(Unit.kg_force)
    UnitGroup.Force.Units.append(Unit.g_force)
    UnitGroup.Force.Units.append(Unit.pdl)
    UnitGroup.Force.Units.append(Unit.lbf)
    UnitGroup.Force.Units.append(Unit.kip)
    UnitGroup.Force.Units.append(Unit.ton_force)

    UnitGroup.Force_per_Velocity.Units.append(Unit.N_s_over_m)
    UnitGroup.Force_per_Velocity.Units.append(Unit.kg_f_s_over_m)
    UnitGroup.Force_per_Velocity.Units.append(Unit.lbf_min_over_ft)

    UnitGroup.Frequency.Units.append(Unit.Hz)
    UnitGroup.Frequency.Units.append(Unit.one_over_s)
    UnitGroup.Frequency.Units.append(Unit.kHz)
    UnitGroup.Frequency.Units.append(Unit.MHz)

    UnitGroup.Heat_Transfer_Coefficient.Units.append(Unit.W_over_m2_K)
    UnitGroup.Heat_Transfer_Coefficient.Units.append(Unit.cal_over_s_cm2_deg_C)
    UnitGroup.Heat_Transfer_Coefficient.Units.append(Unit.kcal_over_h_m2_deg_C)
    UnitGroup.Heat_Transfer_Coefficient.Units.append(Unit.erg_over_s_cm2_deg_C)
    UnitGroup.Heat_Transfer_Coefficient.Units.append(Unit.Btu_over_h_ft2_deg_F)
    UnitGroup.Heat_Transfer_Coefficient.Units.append(Unit.kcal_over_h_ft2_deg_C)
    UnitGroup.Heat_Transfer_Coefficient.Units.append(Unit.kW_over_m2_K)

    UnitGroup.Henrys_Constant.Units.append(Unit.N_over_m2)
    UnitGroup.Henrys_Constant.Units.append(Unit.atm)
    UnitGroup.Henrys_Constant.Units.append(Unit.mmHg)
    UnitGroup.Henrys_Constant.Units.append(Unit.lbf_over_in2)
    UnitGroup.Henrys_Constant.Units.append(Unit.lbf_over_ft2)

    UnitGroup.Inductance.Units.append(Unit.H)
    UnitGroup.Inductance.Units.append(Unit.kg_m2_over_A2_s2)
    UnitGroup.Inductance.Units.append(Unit.V_s_over_A)
    UnitGroup.Inductance.Units.append(Unit.abhenry)
    UnitGroup.Inductance.Units.append(Unit.stathenry)

    UnitGroup.Length.Units.append(Unit.m)
    UnitGroup.Length.Units.append(Unit.cm)
    UnitGroup.Length.Units.append(Unit.µm)
    UnitGroup.Length.Units.append(Unit.mm)
    UnitGroup.Length.Units.append(Unit.km)
    UnitGroup.Length.Units.append(Unit.Å)
    UnitGroup.Length.Units.append(Unit.ft)
    UnitGroup.Length.Units.append(Unit.inch)
    UnitGroup.Length.Units.append(Unit.yd)
    UnitGroup.Length.Units.append(Unit.mi)
    UnitGroup.Length.Units.append(Unit.mils)

    UnitGroup.Magnetic_Flux.Units.append(Unit.Wb)
    UnitGroup.Magnetic_Flux.Units.append(Unit.kg_m2_over_A_s2)
    UnitGroup.Magnetic_Flux.Units.append(Unit.V_s)

    UnitGroup.Mass_per_Area.Units.append(Unit.kg_over_m2)
    UnitGroup.Mass_per_Area.Units.append(Unit.g_over_cm2)
    UnitGroup.Mass_per_Area.Units.append(Unit.lbm_over_ft2)
    UnitGroup.Mass_per_Area.Units.append(Unit.lbm_over_in2)
    UnitGroup.Mass_per_Area.Units.append(Unit.ton_over_mi2)

    UnitGroup.Mass_Per_Mass.Units.append(Unit.g_over_g)
    UnitGroup.Mass_Per_Mass.Units.append(Unit.g_over_kg)
    UnitGroup.Mass_Per_Mass.Units.append(Unit.kg_over_g)
    UnitGroup.Mass_Per_Mass.Units.append(Unit.kg_over_kg)
    UnitGroup.Mass_Per_Mass.Units.append(Unit.g_over_ton)
    UnitGroup.Mass_Per_Mass.Units.append(Unit.kg_over_ton)
    UnitGroup.Mass_Per_Mass.Units.append(Unit.lb_over_lb)
    UnitGroup.Mass_Per_Mass.Units.append(Unit.lb_over_klb)

    UnitGroup.Mass.Units.append(Unit.kg)
    UnitGroup.Mass.Units.append(Unit.g)
    UnitGroup.Mass.Units.append(Unit.ton)
    UnitGroup.Mass.Units.append(Unit.lbm)
    UnitGroup.Mass.Units.append(Unit.klbm)
    UnitGroup.Mass.Units.append(Unit.grain)
    UnitGroup.Mass.Units.append(Unit.oz_avdp)
    UnitGroup.Mass.Units.append(Unit.ton_US)
    UnitGroup.Mass.Units.append(Unit.ton_SI)
    UnitGroup.Mass.Units.append(Unit.slug)

    UnitGroup.Molar_Energy.Units.append(Unit.J_over_mol)
    UnitGroup.Molar_Energy.Units.append(Unit.kJ_over_kmol)
    UnitGroup.Molar_Energy.Units.append(Unit.kJ_over_mol)
    UnitGroup.Molar_Energy.Units.append(Unit.MJ_over_kmol)

    UnitGroup.Molar_Flow.Units.append(Unit.mol_over_s)

    UnitGroup.Molar_Mass.Units.append(Unit.g_over_mol)
    UnitGroup.Molar_Mass.Units.append(Unit.kg_over_mol)
    UnitGroup.Molar_Mass.Units.append(Unit.lbm_over_mol)
    UnitGroup.Molar_Mass.Units.append(Unit.kg_over_kmol)
    UnitGroup.Molar_Mass.Units.append(Unit.lbm_over_kmol)

    UnitGroup.Moment_Inertia_Area.Units.append(Unit.m4)
    UnitGroup.Moment_Inertia_Area.Units.append(Unit.cm4)
    UnitGroup.Moment_Inertia_Area.Units.append(Unit.in4)
    UnitGroup.Moment_Inertia_Area.Units.append(Unit.ft4)

    UnitGroup.Moment_Inertia_Mass.Units.append(Unit.kg_m2)
    UnitGroup.Moment_Inertia_Mass.Units.append(Unit.g_cm2)
    UnitGroup.Moment_Inertia_Mass.Units.append(Unit.lbm_ft2)
    UnitGroup.Moment_Inertia_Mass.Units.append(Unit.lbf_ft_s2)
    UnitGroup.Moment_Inertia_Mass.Units.append(Unit.lbm_in2)
    UnitGroup.Moment_Inertia_Mass.Units.append(Unit.lbf_in_over_s)

    UnitGroup.Momentum_Flow_Rate.Units.append(Unit.kg_m_over_s2)
    UnitGroup.Momentum_Flow_Rate.Units.append(Unit.g_cm_over_s2)
    UnitGroup.Momentum_Flow_Rate.Units.append(Unit.lbm_ft_over_s2)
    UnitGroup.Momentum_Flow_Rate.Units.append(Unit.lbm_ft_over_min2)

    UnitGroup.Momentum_Angular.Units.append(Unit.kg_m2_over_s)
    UnitGroup.Momentum_Angular.Units.append(Unit.g_cm2_over_s)
    UnitGroup.Momentum_Angular.Units.append(Unit.lbm_ft2_over_s)
    UnitGroup.Momentum_Angular.Units.append(Unit.lbm_ft2_over_min)

    UnitGroup.Momentum.Units.append(Unit.kg_m_over_s)
    UnitGroup.Momentum.Units.append(Unit.g_cm_over_s)
    UnitGroup.Momentum.Units.append(Unit.lbm_ft_over_s)
    UnitGroup.Momentum.Units.append(Unit.lbm_ft_over_min)

    UnitGroup._None.Units.append(Unit.none)

    UnitGroup.Power_Density.Units.append(Unit.W_over_m3)
    UnitGroup.Power_Density.Units.append(Unit.kW_over_m3)
    UnitGroup.Power_Density.Units.append(Unit.cal_over_s_cm3)
    UnitGroup.Power_Density.Units.append(Unit.kcal_over_s_cm3)
    UnitGroup.Power_Density.Units.append(Unit.erg_over_s_cm3)
    UnitGroup.Power_Density.Units.append(Unit.ft_lbf_over_s_ft3)
    UnitGroup.Power_Density.Units.append(Unit.Btu_over_s_ft3)
    UnitGroup.Power_Density.Units.append(Unit.Btu_over_h_ft3)
    UnitGroup.Power_Density.Units.append(Unit.kW_over_ft3)
    UnitGroup.Power_Density.Units.append(Unit.hp_over_ft3)

    UnitGroup.Power_Flux.Units.append(Unit.W_over_m2)
    UnitGroup.Power_Flux.Units.append(Unit.kW_over_m2)
    UnitGroup.Power_Flux.Units.append(Unit.cal_over_s_cm2)
    UnitGroup.Power_Flux.Units.append(Unit.kcal_over_s_cm2)
    UnitGroup.Power_Flux.Units.append(Unit.erg_over_s_cm2)
    UnitGroup.Power_Flux.Units.append(Unit.ft_lbf_over_s_ft2)
    UnitGroup.Power_Flux.Units.append(Unit.Btu_over_s_ft2)
    UnitGroup.Power_Flux.Units.append(Unit.Btu_over_h_ft2)
    UnitGroup.Power_Flux.Units.append(Unit.hp_over_ft2)
    UnitGroup.Power_Flux.Units.append(Unit.kW_over_ft2)

    UnitGroup.Power_Linear.Units.append(Unit.W_over_m)
    UnitGroup.Power_Linear.Units.append(Unit.kW_over_m)
    UnitGroup.Power_Linear.Units.append(Unit.cal_over_s_cm)
    UnitGroup.Power_Linear.Units.append(Unit.kcal_over_s_cm)
    UnitGroup.Power_Linear.Units.append(Unit.erg_over_s_cm)
    UnitGroup.Power_Linear.Units.append(Unit.ft_lbf_over_s_ft)
    UnitGroup.Power_Linear.Units.append(Unit.Btu_over_s_ft)
    UnitGroup.Power_Linear.Units.append(Unit.Btu_over_h_ft)
    UnitGroup.Power_Linear.Units.append(Unit.hp_over_ft)

    UnitGroup.Power.Units.append(Unit.W)
    UnitGroup.Power.Units.append(Unit.kW)
    UnitGroup.Power.Units.append(Unit.MW)
    UnitGroup.Power.Units.append(Unit.GW)
    UnitGroup.Power.Units.append(Unit.VA)
    UnitGroup.Power.Units.append(Unit.VAr)
    UnitGroup.Power.Units.append(Unit.kVA)
    UnitGroup.Power.Units.append(Unit.kVAr)
    UnitGroup.Power.Units.append(Unit.MVA)
    UnitGroup.Power.Units.append(Unit.MVAr)
    UnitGroup.Power.Units.append(Unit.cal_over_s)
    UnitGroup.Power.Units.append(Unit.kcal_over_s)
    UnitGroup.Power.Units.append(Unit.erg_over_s)
    UnitGroup.Power.Units.append(Unit.ft_lbf_over_s)
    UnitGroup.Power.Units.append(Unit.Btu_over_h)
    UnitGroup.Power.Units.append(Unit.Btu_over_s)
    UnitGroup.Power.Units.append(Unit.hp)
    UnitGroup.Power.Units.append(Unit.ft_pdl_over_s)
    UnitGroup.Power.Units.append(Unit.in_lbf_over_s)
    UnitGroup.Power.Units.append(Unit.ton_refrigeration)
    UnitGroup.Power.Units.append(Unit.Btu_over_min)

    UnitGroup.Pressure_Massflow_Gradient.Units.append(Unit.Pa_s_over_kg)
    UnitGroup.Pressure_Massflow_Gradient.Units.append(Unit.kPa_s_over_kg)
    UnitGroup.Pressure_Massflow_Gradient.Units.append(Unit.psi_s_over_lbm)

    UnitGroup.Pressure_Stress.Units.append(Unit.N_over_m2)
    UnitGroup.Pressure_Stress.Units.append(Unit.Pa)
    UnitGroup.Pressure_Stress.Units.append(Unit.kPa)
    UnitGroup.Pressure_Stress.Units.append(Unit.MPa)
    UnitGroup.Pressure_Stress.Units.append(Unit.GPa)
    UnitGroup.Pressure_Stress.Units.append(Unit.mPa)
    UnitGroup.Pressure_Stress.Units.append(Unit.Pa_gauge)
    UnitGroup.Pressure_Stress.Units.append(Unit.kPa_gauge)
    UnitGroup.Pressure_Stress.Units.append(Unit.MPa_gauge)
    UnitGroup.Pressure_Stress.Units.append(Unit.psi)
    UnitGroup.Pressure_Stress.Units.append(Unit.psi_gauge)
    UnitGroup.Pressure_Stress.Units.append(Unit.dyn_over_cm2)
    UnitGroup.Pressure_Stress.Units.append(Unit.kg_f_over_cm2)
    UnitGroup.Pressure_Stress.Units.append(Unit.kg_f_over_m2)
    UnitGroup.Pressure_Stress.Units.append(Unit.bar)
    UnitGroup.Pressure_Stress.Units.append(Unit.mbar)
    UnitGroup.Pressure_Stress.Units.append(Unit.std_atm)
    UnitGroup.Pressure_Stress.Units.append(Unit.bar_gauge)
    UnitGroup.Pressure_Stress.Units.append(Unit.mbar_gauge)
    UnitGroup.Pressure_Stress.Units.append(Unit.pdl_over_ft2)
    UnitGroup.Pressure_Stress.Units.append(Unit.lbf_over_ft2)
    UnitGroup.Pressure_Stress.Units.append(Unit.lbf_over_in2)
    UnitGroup.Pressure_Stress.Units.append(Unit.ton_f_over_in2)
    UnitGroup.Pressure_Stress.Units.append(Unit.mm_H2O)
    UnitGroup.Pressure_Stress.Units.append(Unit.cm_H2O)
    UnitGroup.Pressure_Stress.Units.append(Unit.m_H2O)
    UnitGroup.Pressure_Stress.Units.append(Unit.in_H2O)
    UnitGroup.Pressure_Stress.Units.append(Unit.in_H2O_gauge)
    UnitGroup.Pressure_Stress.Units.append(Unit.ft_H2O)
    UnitGroup.Pressure_Stress.Units.append(Unit.mm_Hg)
    UnitGroup.Pressure_Stress.Units.append(Unit.in_Hg)
    UnitGroup.Pressure_Stress.Units.append(Unit.N_over_mm2)
    UnitGroup.Pressure_Stress.Units.append(Unit.lb_over_in2)

    UnitGroup.Resistance.Units.append(Unit.Ohm)
    UnitGroup.Resistance.Units.append(Unit.mOhm)
    UnitGroup.Resistance.Units.append(Unit.kOhm)
    UnitGroup.Resistance.Units.append(Unit.MOhm)
    UnitGroup.Resistance.Units.append(Unit.kg_m2_over_A2_s3)
    UnitGroup.Resistance.Units.append(Unit.V_over_A)
    UnitGroup.Resistance.Units.append(Unit.abohm)
    UnitGroup.Resistance.Units.append(Unit.statohm)

    UnitGroup.Reactivity.Units.append(Unit.mN)
    UnitGroup.Reactivity.Units.append(Unit.percentage)
    UnitGroup.Reactivity.Units.append(Unit.zero_one)

    UnitGroup.Admittance.Units.append(Unit.Siemens)
    UnitGroup.Per_Unit.Units.append(Unit.pu)

    UnitGroup.Specific_Energy.Units.append(Unit.J_over_kg)
    UnitGroup.Specific_Energy.Units.append(Unit.kJ_over_kg)
    UnitGroup.Specific_Energy.Units.append(Unit.MJ_over_kg)
    UnitGroup.Specific_Energy.Units.append(Unit.m2_over_s2)
    UnitGroup.Specific_Energy.Units.append(Unit.cal_over_g)
    UnitGroup.Specific_Energy.Units.append(Unit.kcal_over_g)
    UnitGroup.Specific_Energy.Units.append(Unit.ft_lbf_over_lbm)
    UnitGroup.Specific_Energy.Units.append(Unit.btu_over_lbm)
    UnitGroup.Specific_Energy.Units.append(Unit.hp_h_over_lbm)
    UnitGroup.Specific_Energy.Units.append(Unit.kWh_over_lbm)
    UnitGroup.Specific_Energy.Units.append(Unit.GJ_over_kg)

    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.J_over_kg_K)
    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.kJ_over_kg_K)
    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.MJ_over_kg_K)
    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.m2_over_s2_K)
    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.cal_over_g_K)
    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.erg_over_g_K)
    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.Btu_over_lbm_deg_R)
    UnitGroup.Specific_Heat_Gas_Constant.Units.append(Unit.ft_lbf_over_lbm_deg_R)

    UnitGroup.Specific_Surface.Units.append(Unit.m2_over_kg)
    UnitGroup.Specific_Surface.Units.append(Unit.cm2_over_g)
    UnitGroup.Specific_Surface.Units.append(Unit.µm2_over_lbm)
    UnitGroup.Specific_Surface.Units.append(Unit.ft2_over_lbm)

    UnitGroup.Specific_Volume.Units.append(Unit.m3_over_kg)
    UnitGroup.Specific_Volume.Units.append(Unit.cm3_over_g)
    UnitGroup.Specific_Volume.Units.append(Unit.ft3_over_lbm)
    UnitGroup.Specific_Volume.Units.append(Unit.m3_over_kg)
    UnitGroup.Specific_Volume.Units.append(Unit.cm3_over_g)
    UnitGroup.Specific_Volume.Units.append(Unit.µm3_over_g)
    UnitGroup.Specific_Volume.Units.append(Unit.ft3_over_lbm)

    UnitGroup.Specific_Weight.Units.append(Unit.N_over_m3)
    UnitGroup.Specific_Weight.Units.append(Unit.dyn_over_cm3)
    UnitGroup.Specific_Weight.Units.append(Unit.lbf_over_ft3)

    UnitGroup.Substance_Quantity.Units.append(Unit.mol)

    UnitGroup.Surface_Tension.Units.append(Unit.N_over_m)
    UnitGroup.Surface_Tension.Units.append(Unit.dyn_over_cm)
    UnitGroup.Surface_Tension.Units.append(Unit.lbf_over_ft)
    UnitGroup.Surface_Tension.Units.append(Unit.lbf_over_in)

    UnitGroup.Temperature.Units.append(Unit.K)
    UnitGroup.Temperature.Units.append(Unit.deg_R)
    UnitGroup.Temperature.Units.append(Unit.deg_F)
    UnitGroup.Temperature.Units.append(Unit.deg_C)

    UnitGroup.DifferentialTemperature.Units.append(Unit.Delta_K)
    UnitGroup.DifferentialTemperature.Units.append(Unit.Delta_deg_R)
    UnitGroup.DifferentialTemperature.Units.append(Unit.Delta_deg_F)
    UnitGroup.DifferentialTemperature.Units.append(Unit.Delta_deg_C)

    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.N_over_m2)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_Pa)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_kPa)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_MPa)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_GPa)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_mPa)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_Pa_gauge)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_kPa_gauge)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_MPa_gauge)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_psi)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_psi_gauge)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_dyn_over_cm2)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_kg_f_over_cm2)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_kg_f_over_m2)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_bar)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_mbar)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_std_atm)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_bar_gauge)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_mbar_gauge)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_pdl_over_ft2)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_ton_f_over_in2)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_mm_H2O)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_cm_H2O)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_m_H2O)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_in_H2O)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_in_H2O_gauge)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_ft_H2O)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_mm_Hg)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_in_Hg)
    UnitGroup.DifferentialPressure_Stress.Units.append(Unit.Delta_lb_over_in2)

    UnitGroup.Thermal_Capacitance.Units.append(Unit.J_over_K)
    UnitGroup.Thermal_Capacitance.Units.append(Unit.kJ_over_K)
    UnitGroup.Thermal_Capacitance.Units.append(Unit.MJ_over_K)
    UnitGroup.Thermal_Capacitance.Units.append(Unit.BTU_over_deg_F)
    UnitGroup.Thermal_Capacitance.Units.append(Unit.GJ_over_K)

    UnitGroup.Thermal_Conductivity.Units.append(Unit.W_over_m_K)
    UnitGroup.Thermal_Conductivity.Units.append(Unit.kW_over_m_K)
    UnitGroup.Thermal_Conductivity.Units.append(Unit.cal_over_s_cm_deg_C)
    UnitGroup.Thermal_Conductivity.Units.append(Unit.kcal_over_h_m_deg_C)
    UnitGroup.Thermal_Conductivity.Units.append(Unit.erg_over_s_cm_deg_C)
    UnitGroup.Thermal_Conductivity.Units.append(Unit.Btu_over_h_ft_deg_F)
    UnitGroup.Thermal_Conductivity.Units.append(Unit.Btu_in_over_h_ft2_deg_F)
    UnitGroup.Thermal_Conductivity.Units.append(Unit.ft_lbf_over_h_ft_deg_F)

    UnitGroup.Thermal_Resistance.Units.append(Unit.m2_K_over_W)
    UnitGroup.Thermal_Resistance.Units.append(Unit.m2_K_over_kW)
    UnitGroup.Thermal_Resistance.Units.append(Unit.h_ft2_deg_F_over_Btu)

    UnitGroup.Thermal_Expansion.Units.append(Unit.one_over_K)
    UnitGroup.Thermal_Expansion.Units.append(Unit.one_over_deg_C)
    UnitGroup.Thermal_Expansion.Units.append(Unit.one_over_deg_F)

    UnitGroup.Time.Units.append(Unit.ms)
    UnitGroup.Time.Units.append(Unit.s)
    UnitGroup.Time.Units.append(Unit.min)
    UnitGroup.Time.Units.append(Unit.h)
    UnitGroup.Time.Units.append(Unit.day)
    UnitGroup.Time.Units.append(Unit.yr)

    UnitGroup.Turbine_Loss_Coefficient.Units.append(Unit.one_over_m4)
    UnitGroup.Turbine_Loss_Coefficient.Units.append(Unit.one_over_ft4)
    UnitGroup.Turbine_Loss_Coefficient.Units.append(Unit.one_over_in4)

    UnitGroup.Torque.Units.append(Unit.N_m)
    UnitGroup.Torque.Units.append(Unit.dyn_cm)
    UnitGroup.Torque.Units.append(Unit.lbf_ft)
    UnitGroup.Torque.Units.append(Unit.pdl_ft)
    UnitGroup.Torque.Units.append(Unit.kg_f_ft)

    UnitGroup.Velocity_Angular.Units.append(Unit.rad_over_s)
    UnitGroup.Velocity_Angular.Units.append(Unit.rad_over_min)
    UnitGroup.Velocity_Angular.Units.append(Unit.rad_over_h)
    UnitGroup.Velocity_Angular.Units.append(Unit.rev_over_min)
    UnitGroup.Velocity_Angular.Units.append(Unit.rpm)
    UnitGroup.Velocity_Angular.Units.append(Unit.rps)

    UnitGroup.Velocity.Units.append(Unit.m_over_s)
    UnitGroup.Velocity.Units.append(Unit.mm_over_s)
    UnitGroup.Velocity.Units.append(Unit.cm_over_s)
    UnitGroup.Velocity.Units.append(Unit.m_over_h)
    UnitGroup.Velocity.Units.append(Unit.km_over_h)
    UnitGroup.Velocity.Units.append(Unit.in_over_s)
    UnitGroup.Velocity.Units.append(Unit.ft_over_s)
    UnitGroup.Velocity.Units.append(Unit.ft_over_min)
    UnitGroup.Velocity.Units.append(Unit.mi_over_h)

    UnitGroup.Viscosity_Dynamic.Units.append(Unit.kg_over_m_s)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.N_s_over_m2)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.P)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.cP)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.kg_over_m_h)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.lbm_over_ft_s)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.lbm_over_ft_h)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.lbf_s_over_ft2)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.Pa_s)
    UnitGroup.Viscosity_Dynamic.Units.append(Unit.mPa_s)

    UnitGroup.Viscosity_Kinematic.Units.append(Unit.m2_over_s)
    UnitGroup.Viscosity_Kinematic.Units.append(Unit.St)
    UnitGroup.Viscosity_Kinematic.Units.append(Unit.m2_over_h)
    UnitGroup.Viscosity_Kinematic.Units.append(Unit.ft2_over_s)
    UnitGroup.Viscosity_Kinematic.Units.append(Unit.ft2_over_h)

    UnitGroup.Voltage_Electrical_Potential.Units.append(Unit.V)
    UnitGroup.Voltage_Electrical_Potential.Units.append(Unit.kV)
    UnitGroup.Voltage_Electrical_Potential.Units.append(Unit.MV)
    UnitGroup.Voltage_Electrical_Potential.Units.append(Unit.kg_m2_over_A_s3)
    UnitGroup.Voltage_Electrical_Potential.Units.append(Unit.W_over_A)
    UnitGroup.Voltage_Electrical_Potential.Units.append(Unit.abvolt)
    UnitGroup.Voltage_Electrical_Potential.Units.append(Unit.statvolt)

    UnitGroup.Volume.Units.append(Unit.m3)
    UnitGroup.Volume.Units.append(Unit.cm3)
    UnitGroup.Volume.Units.append(Unit.l)
    UnitGroup.Volume.Units.append(Unit.kl)
    UnitGroup.Volume.Units.append(Unit.Ml)
    UnitGroup.Volume.Units.append(Unit.Gl)
    UnitGroup.Volume.Units.append(Unit.µm3)
    UnitGroup.Volume.Units.append(Unit.ft3)
    UnitGroup.Volume.Units.append(Unit.in3)
    UnitGroup.Volume.Units.append(Unit.gal_US)

    UnitGroup.Volume_Per_Volume.Units.append(Unit.m3_over_m3)
    UnitGroup.Volume_Per_Volume.Units.append(Unit.l_over_l)
    UnitGroup.Volume_Per_Volume.Units.append(Unit.l_over_m3)
    UnitGroup.Volume_Per_Volume.Units.append(Unit.ft3_over_ft3)
    UnitGroup.Volume_Per_Volume.Units.append(Unit.gal_US_over_gal_US)
    UnitGroup.Volume_Per_Volume.Units.append(Unit.gal_US_over_ft3)

    UnitGroup.Volumetric_Thermal_Capacitance.Units.append(Unit.J_over_m3_K)
    UnitGroup.Volumetric_Thermal_Capacitance.Units.append(Unit.kJ_over_m3_K)
    UnitGroup.Volumetric_Thermal_Capacitance.Units.append(Unit.MJ_over_m3_K)
    UnitGroup.Volumetric_Thermal_Capacitance.Units.append(Unit.BTU_over_ft3_deg_F)
    UnitGroup.Volumetric_Thermal_Capacitance.Units.append(Unit.GJ_over_m3_K)

    UnitGroup.AtkinsonResistance.Units.append(Unit.kg_over_meter7)
    UnitGroup.AtkinsonResistance.Units.append(Unit.lb_over_inch7)
    UnitGroup.AtkinsonResistance.Units.append(Unit.lb_over_feet7)

_populate_units()

def _populate_SI_units():
    UnitGroup.SIUnits.append(Unit.rad_over_s2)
    UnitGroup.SIUnits.append(Unit.m_over_s2)
    UnitGroup.SIUnits.append(Unit.one_over_m_over_s2)
    UnitGroup.SIUnits.append(Unit.rad)
    UnitGroup.SIUnits.append( Unit.m2)
    UnitGroup.SIUnits.append(Unit.W_over_K)
    UnitGroup.SIUnits.append( Unit.A)
    UnitGroup.SIUnits.append(Unit.kg_over_s_sqrt_K_over_Pa)
    UnitGroup.SIUnits.append( Unit.kg_over_m3)
    UnitGroup.SIUnits.append(Unit.m2_over_s)
    UnitGroup.SIUnits.append(Unit.zero_one)
    UnitGroup.SIUnits.append(Unit.F)
    UnitGroup.SIUnits.append(Unit.C)
    UnitGroup.SIUnits.append(Unit.V_over_m)
    UnitGroup.SIUnits.append(Unit.ohm_m)
    UnitGroup.SIUnits.append(Unit.J_over_m3)
    UnitGroup.SIUnits.append( Unit.J_over_m2)
    UnitGroup.SIUnits.append( Unit.J_over_m)
    UnitGroup.SIUnits.append(Unit.J)
    UnitGroup.SIUnits.append(Unit.m3_over_h_sqrt_Bar)
    UnitGroup.SIUnits.append(Unit.m3_over_h_sqrt_Bar_over_msquared)
    UnitGroup.SIUnits.append(Unit.kg_over_N_s)
    UnitGroup.SIUnits.append( Unit.kg_over_m3_s)
    UnitGroup.SIUnits.append(Unit.kg_over_s)
    UnitGroup.SIUnits.append(Unit.m3_over_s)
    UnitGroup.SIUnits.append(Unit.kg_over_m2_s)
    UnitGroup.SIUnits.append(Unit.N_over_kg)
    UnitGroup.SIUnits.append(Unit.N_over_m3)
    UnitGroup.SIUnits.append(Unit.N)
    UnitGroup.SIUnits.append(Unit.N_s_over_m)
    UnitGroup.SIUnits.append(Unit.Hz)
    UnitGroup.SIUnits.append(Unit.W_over_m2_K)
    UnitGroup.SIUnits.append(Unit.N_over_m2)
    UnitGroup.SIUnits.append(Unit.H)
    UnitGroup.SIUnits.append(Unit.m)
    UnitGroup.SIUnits.append(Unit.Wb)
    UnitGroup.SIUnits.append(Unit.kg_over_m2)
    UnitGroup.SIUnits.append(Unit.kg_over_kg)
    UnitGroup.SIUnits.append(Unit.kg)
    UnitGroup.SIUnits.append(Unit.J_over_mol)
    UnitGroup.SIUnits.append(Unit.mol_over_s)
    UnitGroup.SIUnits.append(Unit.kg_over_mol)
    UnitGroup.SIUnits.append(Unit.m4)
    UnitGroup.SIUnits.append(Unit.kg_m2)
    UnitGroup.SIUnits.append(Unit.kg_m_over_s2)
    UnitGroup.SIUnits.append(Unit.kg_m2_over_s)
    UnitGroup.SIUnits.append(Unit.kg_m_over_s)
    UnitGroup.SIUnits.append(Unit.none)
    UnitGroup.SIUnits.append(Unit.W_over_m3)
    UnitGroup.SIUnits.append(Unit.W_over_m2)
    UnitGroup.SIUnits.append(Unit.W_over_m)
    UnitGroup.SIUnits.append(Unit.W)
    UnitGroup.SIUnits.append(Unit.Pa)
    UnitGroup.SIUnits.append(Unit.Ohm)
    UnitGroup.SIUnits.append(Unit.zero_one)
    UnitGroup.SIUnits.append(Unit.Siemens)
    UnitGroup.SIUnits.append(Unit.pu)
    UnitGroup.SIUnits.append(Unit.J_over_kg)
    UnitGroup.SIUnits.append(Unit.J_over_kg_K)
    UnitGroup.SIUnits.append(Unit.m2_over_kg)
    UnitGroup.SIUnits.append(Unit.m3_over_kg)
    UnitGroup.SIUnits.append(Unit.N_over_m3)
    UnitGroup.SIUnits.append(Unit.mol)
    UnitGroup.SIUnits.append(Unit.N_over_m)
    UnitGroup.SIUnits.append(Unit.K)
    UnitGroup.SIUnits.append(Unit.Delta_K)
    UnitGroup.SIUnits.append(Unit.Delta_Pa)
    UnitGroup.SIUnits.append(Unit.J_over_K)
    UnitGroup.SIUnits.append(Unit.W_over_m_K)
    UnitGroup.SIUnits.append(Unit.one_over_K)
    UnitGroup.SIUnits.append(Unit.m2_K_over_W)
    UnitGroup.SIUnits.append(Unit.s)
    UnitGroup.SIUnits.append(Unit.one_over_m4)
    UnitGroup.SIUnits.append(Unit.N_m)
    UnitGroup.SIUnits.append(Unit.rad_over_s)
    UnitGroup.SIUnits.append(Unit.m_over_s)
    UnitGroup.SIUnits.append(Unit.kg_over_m_s)
    UnitGroup.SIUnits.append(Unit.m2_over_s)
    UnitGroup.SIUnits.append(Unit.V)
    UnitGroup.SIUnits.append(Unit.m3)
    UnitGroup.SIUnits.append(Unit.m3_over_m3)
    UnitGroup.SIUnits.append(Unit.J_over_m3_K)
    UnitGroup.SIUnits.append(Unit.kg_over_meter7)
    UnitGroup.SIUnits.append(Unit.Pa_s_over_kg)

_populate_SI_units()