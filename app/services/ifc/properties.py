from typing import Dict, Optional, List
import ifcopenshell
from functools import lru_cache
from datetime import datetime
import gc

def clear_property_caches():
    """Clear all LRU caches to free memory"""
    get_element_property.cache_clear()
    get_common_properties.cache_clear()
    gc.collect()

@lru_cache(maxsize=128)
def get_element_property(element, property_name: str) -> Optional[str]:
    """Get property from element's property sets."""
    element_class = element.is_a()[3:]
    pset_name = f"Pset_{element_class}Common"
    return ifcopenshell.util.element.get_pset(element, pset_name, property_name) or \
           ifcopenshell.util.element.get_pset(element, "Pset_ElementCommon", property_name)

def get_containment_structure(element) -> Dict:
    """Get the spatial containment structure for an element (building, storey, space)."""
    structure = {
        "building": None,
        "storey": None,
        "space": None
    }
    
    # Try to get containment information through decomposition
    if hasattr(element, "ContainedInStructure"):
        for rel in element.ContainedInStructure:
            if not rel.is_a("IfcRelContainedInSpatialStructure"):
                continue
                
            container = rel.RelatingStructure
            if not container:
                continue
                
            if container.is_a("IfcBuildingStorey"):
                structure["storey"] = {
                    "id": container.GlobalId,
                    "name": container.Name,
                    "elevation": container.Elevation if hasattr(container, "Elevation") else None,
                    "description": container.Description
                }
                
                # Get building information
                if hasattr(container, "Decomposes"):
                    for rel in container.Decomposes:
                        if rel.is_a("IfcRelAggregates"):
                            building = rel.RelatingObject
                            if building and building.is_a("IfcBuilding"):
                                structure["building"] = {
                                    "id": building.GlobalId,
                                    "name": building.Name,
                                    "description": building.Description
                                }
                                break
            
            elif container.is_a("IfcSpace"):
                structure["space"] = {
                    "id": container.GlobalId,
                    "name": container.Name,
                    "description": container.Description
                }
                
                # Try to get storey and building through space containment
                if hasattr(container, "Decomposes"):
                    for rel in container.Decomposes:
                        if rel.is_a("IfcRelAggregates"):
                            storey = rel.RelatingObject
                            if storey and storey.is_a("IfcBuildingStorey"):
                                structure["storey"] = {
                                    "id": storey.GlobalId,
                                    "name": storey.Name,
                                    "elevation": storey.Elevation if hasattr(storey, "Elevation") else None,
                                    "description": storey.Description
                                }
                                
                                # Get building information
                                if hasattr(storey, "Decomposes"):
                                    for rel2 in storey.Decomposes:
                                        if rel2.is_a("IfcRelAggregates"):
                                            building = rel2.RelatingObject
                                            if building and building.is_a("IfcBuilding"):
                                                structure["building"] = {
                                                    "id": building.GlobalId,
                                                    "name": building.Name,
                                                    "description": building.Description
                                                }
                                                break
                                break
    
    # Remove None values for cleaner output
    return {k: v for k, v in structure.items() if v is not None}

@lru_cache(maxsize=128)
def get_common_properties(element) -> Dict:
    """Get common properties for an element including description, fire rating, etc."""
    properties = {
        "loadBearing": None,
        "isExternal": None,
        "description": None,
        "fireRating": None,
        "reference": None,
        "status": None,
        "thermalTransmittance": None,
        "acousticRating": None,
        "combustible": None,
        "surfaceSpreadOfFlame": None,
        "extendToStructure": None,
        "compartmentation": None,
        "phase": None,
        "manufacturer": None,
        "model": None,
        "serialNumber": None,
        "installationDate": None,
        "constructionMethod": None,
        "customProperties": {},
        "containment": get_containment_structure(element)
    }
    
    element_class = element.is_a()[3:]
    pset_name = f"Pset_{element_class}Common"
    
    # Property mapping with type conversion
    property_mapping = {
        "LoadBearing": ("loadBearing", bool),
        "IsExternal": ("isExternal", bool),
        "Description": ("description", str),
        "FireRating": ("fireRating", str),
        "Reference": ("reference", str),
        "Status": ("status", str),
        "ThermalTransmittance": ("thermalTransmittance", float),
        "AcousticRating": ("acousticRating", str),
        "Combustible": ("combustible", bool),
        "SurfaceSpreadOfFlame": ("surfaceSpreadOfFlame", str),
        "ExtendToStructure": ("extendToStructure", bool),
        "Compartmentation": ("compartmentation", bool),
        "Phase": ("phase", str),
        "Manufacturer": ("manufacturer", str),
        "ModelReference": ("model", str),
        "SerialNumber": ("serialNumber", str),
        "InstallationDate": ("installationDate", str),
        "ConstructionMethod": ("constructionMethod", str)
    }
    
    for rel in element.IsDefinedBy:
        if rel.is_a('IfcRelDefinesByProperties'):
            pset = rel.RelatingPropertyDefinition
            if pset.is_a('IfcPropertySet'):
                # Process common property sets
                if pset.Name == pset_name or pset.Name == "Pset_ElementCommon":
                    for prop in pset.HasProperties:
                        if prop.Name in property_mapping:
                            key, type_conv = property_mapping[prop.Name]
                            if hasattr(prop, "NominalValue"):
                                try:
                                    value = getattr(prop.NominalValue, "wrappedValue", None)
                                    if value is not None:
                                        properties[key] = type_conv(value)
                                except (ValueError, TypeError):
                                    continue
                else:
                    # Store other properties in customProperties
                    for prop in pset.HasProperties:
                        if hasattr(prop, "NominalValue"):
                            try:
                                value = getattr(prop.NominalValue, "wrappedValue", None)
                                if value is not None:
                                    if pset.Name not in properties["customProperties"]:
                                        properties["customProperties"][pset.Name] = {}
                                    properties["customProperties"][pset.Name][prop.Name] = value
                            except (ValueError, TypeError):
                                continue
    
    # Remove empty custom properties
    if not properties["customProperties"]:
        properties.pop("customProperties")
    
    # Remove None values for cleaner output
    return {k: v for k, v in properties.items() if v is not None}

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

def get_model_metadata(ifc_file) -> Dict:
    """Get metadata about the IFC model including author, organization, timestamps, etc."""
    metadata = {
        "schema": ifc_file.schema,
        "header": {
            "description": ifc_file.header.file_description.description,
            "implementation_level": ifc_file.header.file_description.implementation_level,
            "name": ifc_file.header.file_name.name,
            "time_stamp": ifc_file.header.file_name.time_stamp,
            "author": ifc_file.header.file_name.author,
            "organization": ifc_file.header.file_name.organization,
            "preprocessor_version": ifc_file.header.file_name.preprocessor_version,
            "originating_system": ifc_file.header.file_name.originating_system,
            "authorization": ifc_file.header.file_name.authorization
        },
        "project": {}
    }

    # Get project information
    project = ifc_file.by_type("IfcProject")[0] if ifc_file.by_type("IfcProject") else None
    if project:
        metadata["project"] = {
            "name": project.Name,
            "description": project.Description,
            "phase": project.Phase,
            "units": {unit.Name for unit in ifc_file.by_type("IfcSIUnit")} if ifc_file.by_type("IfcSIUnit") else set()
        }
        
        # Get owner history information if available
        if project.OwnerHistory:
            owner_history = project.OwnerHistory
            metadata["project"]["owner_history"] = {
                "creation_date": datetime.fromtimestamp(owner_history.CreationDate).isoformat() if owner_history.CreationDate else None,
                "last_modified_date": datetime.fromtimestamp(owner_history.LastModifiedDate).isoformat() if owner_history.LastModifiedDate else None,
                "author": owner_history.OwningUser.ThePerson.FamilyName if owner_history.OwningUser and owner_history.OwningUser.ThePerson else None,
                "organization": owner_history.OwningUser.TheOrganization.Name if owner_history.OwningUser and owner_history.OwningUser.TheOrganization else None,
                "application": {
                    "name": owner_history.OwningApplication.ApplicationFullName if owner_history.OwningApplication else None,
                    "version": owner_history.OwningApplication.Version if owner_history.OwningApplication else None,
                    "identifier": owner_history.OwningApplication.ApplicationIdentifier if owner_history.OwningApplication else None
                }
            }
    
    # Remove None values for cleaner output
    return {k: v for k, v in metadata.items() if v is not None} 