from typing import Dict, Any, Optional, Union
from enum import Enum

class LengthUnit(str, Enum):
    ATTOMETER = "ATTOMETER"
    FEMTOMETER = "FEMTOMETER"
    PICOMETER = "PICOMETER"
    NANOMETER = "NANOMETER"
    MICROMETER = "MICROMETER"
    MILLIMETER = "MILLIMETER"
    CENTIMETER = "CENTIMETER"
    DECIMETER = "DECIMETER"
    METER = "METER"
    DECAMETER = "DECAMETER"
    HECTOMETER = "HECTOMETER"
    KILOMETER = "KILOMETER"
    MEGAMETER = "MEGAMETER"
    GIGAMETER = "GIGAMETER"
    TERAMETER = "TERAMETER"
    PETAMETER = "PETAMETER"
    EXAMETER = "EXAMETER"
    INCH = "INCH"
    FOOT = "FOOT"
    MILE = "MILE"

def get_project_units(ifc_file) -> Dict[str, Any]:
    """Get all project units from IFC file."""
    units = {}
    project = ifc_file.by_type("IfcProject")[0]
    for context in project.UnitsInContext.Units:
        if context.is_a("IfcSIUnit"):
            units[context.UnitType] = {
                "type": context.UnitType,
                "name": context.Name,
                "prefix": getattr(context, "Prefix", None),
            }
        elif context.is_a("IfcConversionBasedUnit"):
            units[context.UnitType] = {
                "type": context.UnitType,
                "name": context.Name,
                "conversion_factor": context.ConversionFactor.ValueComponent,
            }
    return units

def convert_unit_value(value: Union[float, Dict[str, float]], 
                      source_unit: Dict[str, Any], 
                      target_unit: LengthUnit = LengthUnit.METER) -> Union[float, Dict[str, float]]:
    """Convert a value to meters.
    
    Args:
        value: The value or dictionary of values to convert
        source_unit: The source unit information from IFC
        target_unit: The target unit (default: METER)
        
    Returns:
        The converted value(s) in meters
    """
    if isinstance(value, dict):
        return {
            k: convert_unit_value(v, source_unit, target_unit)
            for k, v in value.items()
            if v is not None
        }
    
    if value is None:
        return None
        
    # Get base conversion factor
    factor = 1.0
    if source_unit.get("prefix"):
        # Handle SI unit prefixes
        prefix_factors = {
            "EXA": 1e18,
            "PETA": 1e15,
            "TERA": 1e12,
            "GIGA": 1e9,
            "MEGA": 1e6,
            "KILO": 1e3,
            "HECTO": 1e2,
            "DECA": 1e1,
            "DECI": 1e-1,
            "CENTI": 1e-2,
            "MILLI": 1e-3,
            "MICRO": 1e-6,
            "NANO": 1e-9,
            "PICO": 1e-12,
            "FEMTO": 1e-15,
            "ATTO": 1e-18
        }
        factor *= prefix_factors.get(source_unit["prefix"], 1.0)
    
    # Apply any conversion factor for non-SI units
    if "conversion_factor" in source_unit:
        factor *= source_unit["conversion_factor"]
    
    return value * factor