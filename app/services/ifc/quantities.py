from typing import Dict
from functools import lru_cache
from .properties import get_element_property, clear_property_caches

def clear_quantity_caches():
    """Clear all quantity-related caches"""
    get_volume_from_basequantities.cache_clear()
    get_area_from_basequantities.cache_clear()
    get_dimensions_from_basequantities.cache_clear()
    clear_property_caches()

@lru_cache(maxsize=128)
def get_volume_from_basequantities(element) -> Dict:
    """Get volume quantities from base quantities."""
    net_volume = None
    gross_volume = None
    
    for rel_def in element.IsDefinedBy:
        if rel_def.is_a("IfcRelDefinesByProperties"):
            prop_set = rel_def.RelatingPropertyDefinition
            if prop_set.is_a("IfcElementQuantity"):
                for quantity in prop_set.Quantities:
                    if quantity.is_a("IfcQuantityVolume"):
                        try:
                            if quantity.Name == "NetVolume":
                                net_volume = float(quantity.VolumeValue)
                            elif quantity.Name == "GrossVolume":
                                gross_volume = float(quantity.VolumeValue)
                        except (ValueError, AttributeError):
                            continue
                    elif quantity.is_a("IfcQuantityLength"):
                        try:
                            if quantity.Name == "NetVolume":
                                net_volume = float(quantity.LengthValue)
                            elif quantity.Name == "GrossVolume":
                                gross_volume = float(quantity.LengthValue)
                        except (ValueError, AttributeError):
                            continue
    
    return {"net": net_volume, "gross": gross_volume}

@lru_cache(maxsize=128)
def get_area_from_basequantities(element) -> Dict:
    """Get area quantities from base quantities."""
    net_area = None
    gross_area = None
    
    for rel_def in element.IsDefinedBy:
        if rel_def.is_a("IfcRelDefinesByProperties"):
            prop_set = rel_def.RelatingPropertyDefinition
            if prop_set.is_a("IfcElementQuantity"):
                for quantity in prop_set.Quantities:
                    if quantity.is_a("IfcQuantityArea"):
                        try:
                            if quantity.Name in ["NetArea", "NetSideArea"]:
                                net_area = float(quantity.AreaValue)
                            elif quantity.Name in ["GrossArea", "GrossSideArea"]:
                                gross_area = float(quantity.AreaValue)
                        except (ValueError, AttributeError):
                            continue
    
    return {"net": net_area, "gross": gross_area}

@lru_cache(maxsize=128)
def get_dimensions_from_basequantities(element) -> Dict:
    """Get dimensional quantities from base quantities."""
    dimensions = {
        "length": None,
        "width": None,
        "height": None
    }
    
    for rel_def in element.IsDefinedBy:
        if rel_def.is_a("IfcRelDefinesByProperties"):
            prop_set = rel_def.RelatingPropertyDefinition
            if prop_set.is_a("IfcElementQuantity"):
                for quantity in prop_set.Quantities:
                    if quantity.is_a("IfcQuantityLength"):
                        try:
                            if quantity.Name == "Length":
                                dimensions["length"] = float(quantity.LengthValue)
                            elif quantity.Name in ["Width", "Thickness"]:
                                dimensions["width"] = float(quantity.LengthValue)
                            elif quantity.Name == "Height":
                                dimensions["height"] = float(quantity.LengthValue)
                        except (ValueError, AttributeError):
                            continue
    
    return dimensions

def get_volume_from_properties(element) -> Dict:
    """Get volumes from properties or base quantities."""
    volumes = get_volume_from_basequantities(element)
    if volumes["net"] is not None or volumes["gross"] is not None:
        return volumes

    net_volume = get_element_property(element, "NetVolume")
    gross_volume = get_element_property(element, "GrossVolume")
    
    try:
        net_volume = float(net_volume) if net_volume else None
        gross_volume = float(gross_volume) if gross_volume else None
    except ValueError:
        net_volume = None
        gross_volume = None

    return {"net": net_volume, "gross": gross_volume}

def get_area_from_properties(element) -> Dict:
    """Get areas from properties or base quantities."""
    areas = get_area_from_basequantities(element)
    if areas["net"] is not None or areas["gross"] is not None:
        return areas

    net_area = get_element_property(element, "NetArea") or get_element_property(element, "NetSideArea")
    gross_area = get_element_property(element, "GrossArea") or get_element_property(element, "GrossSideArea")
    
    try:
        net_area = float(net_area) if net_area else None
        gross_area = float(gross_area) if gross_area else None
    except ValueError:
        net_area = None
        gross_area = None

    return {"net": net_area, "gross": gross_area}

def get_dimensions_from_properties(element) -> Dict:
    """Get dimensions from properties or base quantities."""
    dimensions = get_dimensions_from_basequantities(element)
    if any(dimensions.values()):
        return dimensions

    try:
        length = get_element_property(element, "Length")
        width = get_element_property(element, "Width") or get_element_property(element, "Thickness")
        height = get_element_property(element, "Height")
        
        dimensions["length"] = float(length) if length else None
        dimensions["width"] = float(width) if width else None
        dimensions["height"] = float(height) if height else None
    except (ValueError, AttributeError):
        pass

    return dimensions 