from typing import Dict, Optional
import ifcopenshell
from functools import lru_cache

@lru_cache(maxsize=1024)
def get_element_property(element, property_name: str) -> Optional[str]:
    """Get property from element's property sets."""
    element_class = element.is_a()[3:]
    pset_name = f"Pset_{element_class}Common"
    return ifcopenshell.util.element.get_pset(element, pset_name, property_name) or \
           ifcopenshell.util.element.get_pset(element, "Pset_ElementCommon", property_name)

@lru_cache(maxsize=1024)
def get_common_properties(element) -> Dict:
    """Get common properties like LoadBearing and IsExternal."""
    properties = {
        "loadBearing": None,
        "isExternal": None
    }
    
    element_class = element.is_a()[3:]
    pset_name = f"Pset_{element_class}Common"
    
    for rel in element.IsDefinedBy:
        if rel.is_a('IfcRelDefinesByProperties'):
            pset = rel.RelatingPropertyDefinition
            if pset.is_a('IfcPropertySet'):
                if pset.Name == pset_name or pset.Name == "Pset_ElementCommon":
                    for prop in pset.HasProperties:
                        if prop.Name == "LoadBearing":
                            properties["loadBearing"] = bool(getattr(prop, "NominalValue", None).wrappedValue) if hasattr(prop, "NominalValue") else None
                        elif prop.Name == "IsExternal":
                            properties["isExternal"] = bool(getattr(prop, "NominalValue", None).wrappedValue) if hasattr(prop, "NominalValue") else None
    
    return properties

@lru_cache(maxsize=1024)
def get_object_type(element) -> Optional[str]:
    """Get the object type of an element."""
    if hasattr(element, "IsTypedBy"):
        for rel in element.IsTypedBy:
            if rel.is_a("IfcRelDefinesByType"):
                type_object = rel.RelatingType
                if type_object:
                    return type_object.Name if hasattr(type_object, "Name") else None
    return None 