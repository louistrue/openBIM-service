from typing import Dict, Any, Optional
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