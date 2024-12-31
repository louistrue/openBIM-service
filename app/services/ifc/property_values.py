from typing import Dict, List, Optional, Tuple, Union
import ifcopenshell
from dataclasses import dataclass
from functools import lru_cache
import re

@dataclass
class PropertyValue:
    """Data class to store property value information"""
    guid: str
    value: Optional[Union[str, float, int, bool]]
    data_type: str

def parse_property_path(property_path: str) -> Tuple[str, str]:
    """Parse property path into pset name and property name"""
    try:
        pset_name, property_name = property_path.split(".", 1)
        return pset_name.strip(), property_name.strip()
    except ValueError:
        raise ValueError("Property path must be in format 'PsetName.PropertyName'")

@lru_cache(maxsize=128)
def get_property_type(property_value) -> str:
    """Determine the IFC data type of a property value"""
    if hasattr(property_value, "is_a"):
        return property_value.is_a()
    elif isinstance(property_value, bool):
        return "IfcBoolean"
    elif isinstance(property_value, int):
        return "IfcInteger"
    elif isinstance(property_value, float):
        return "IfcReal"
    elif isinstance(property_value, str):
        return "IfcLabel"
    return "IfcLabel"  # Default fallback

def get_matching_psets(element, pset_pattern: str) -> List[str]:
    """Get property set names matching the pattern"""
    if '*' not in pset_pattern:
        return [pset_pattern]
        
    # Convert glob pattern to regex pattern
    regex_pattern = re.compile(pset_pattern.replace('*', '.*'))
    
    matching_psets = []
    for rel in element.IsDefinedBy:
        if rel.is_a('IfcRelDefinesByProperties'):
            pset = rel.RelatingPropertyDefinition
            if pset.is_a('IfcPropertySet') and regex_pattern.match(pset.Name):
                matching_psets.append(pset.Name)
                
    return matching_psets

def get_property_values(
    ifc_file: ifcopenshell.file,
    ifc_class: str,
    property_path: str
) -> List[PropertyValue]:
    """
    Get property values for all elements of a specific IFC class.
    
    Args:
        ifc_file: The IFC file to query
        ifc_class: The IFC class name (e.g., 'IfcWall')
        property_path: Property path in format 'PsetName.PropertyName'
                      Supports wildcards in PsetName (e.g., '*Common.LoadBearing')
        
    Returns:
        List of PropertyValue objects containing guid, value and data type
    """
    pset_name, property_name = parse_property_path(property_path)
    
    # Get all elements of the specified class
    elements = ifc_file.by_type(ifc_class)
    if not elements:
        return []
        
    results: List[PropertyValue] = []
    
    # Use IfcOpenShell's optimized property getter
    for element in elements:
        if not hasattr(element, "GlobalId"):
            continue
            
        # Handle wildcard in property set name
        matching_psets = get_matching_psets(element, pset_name)
        
        for pset_name in matching_psets:
            # Get property value using IfcOpenShell utility
            prop_value = ifcopenshell.util.element.get_pset(
                element, 
                pset_name,
                property_name
            )
            
            if prop_value is not None:
                # Handle wrapped IFC values
                if hasattr(prop_value, "wrappedValue"):
                    prop_value = prop_value.wrappedValue
                    
                results.append(PropertyValue(
                    guid=element.GlobalId,
                    value=prop_value,
                    data_type=get_property_type(prop_value)
                ))
                break  # Stop after first match for this element
    
    return results