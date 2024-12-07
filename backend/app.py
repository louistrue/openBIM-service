from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ifcopenshell
import ifcopenshell.util.element
from ifcopenshell.util.unit import calculate_unit_scale
import tempfile
import os
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import asyncio
from fastapi.responses import StreamingResponse
import json
import multiprocessing
from multiprocessing import Manager, Value
import ctypes
from typing import Literal, Optional, Dict, Any
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache volume calculations for elements with same properties
@lru_cache(maxsize=1024)
def get_volume_from_basequantities(element):
    net_volume = None
    gross_volume = None
    
    for rel_def in element.IsDefinedBy:
        if rel_def.is_a("IfcRelDefinesByProperties"):
            prop_set = rel_def.RelatingPropertyDefinition
            if prop_set.is_a("IfcElementQuantity"):
                for quantity in prop_set.Quantities:
                    # Handle volume quantities
                    if quantity.is_a("IfcQuantityVolume"):
                        try:
                            if quantity.Name == "NetVolume":
                                net_volume = float(quantity.VolumeValue)
                            elif quantity.Name == "GrossVolume":
                                gross_volume = float(quantity.VolumeValue)
                        except (ValueError, AttributeError):
                            continue
                    
                    # Handle length-based quantities
                    elif quantity.is_a("IfcQuantityLength"):
                        try:
                            if quantity.Name == "NetVolume":
                                net_volume = float(quantity.LengthValue)
                            elif quantity.Name == "GrossVolume":
                                gross_volume = float(quantity.LengthValue)
                        except (ValueError, AttributeError):
                            continue
    
    return {"net": net_volume, "gross": gross_volume}

# Cache property lookups
@lru_cache(maxsize=1024)
def get_element_property(element, property_name):
    element_class = element.is_a()[3:]
    pset_name = f"Pset_{element_class}Common"
    return ifcopenshell.util.element.get_pset(element, pset_name, property_name) or \
           ifcopenshell.util.element.get_pset(element, "Pset_ElementCommon", property_name)

def get_volume_from_properties(element):
    # First try to get volumes from BaseQuantities
    volumes = get_volume_from_basequantities(element)
    if volumes["net"] is not None or volumes["gross"] is not None:
        return volumes

    # If no volumes found in BaseQuantities, try properties
    net_volume = get_element_property(element, "NetVolume")
    gross_volume = get_element_property(element, "GrossVolume")
    
    try:
        net_volume = float(net_volume) if net_volume else None
        gross_volume = float(gross_volume) if gross_volume else None
    except ValueError:
        net_volume = None
        gross_volume = None

    return {"net": net_volume, "gross": gross_volume}

def compute_constituent_fractions(model, constituent_set, associated_elements, unit_scale_to_mm):
    fractions = {}
    constituents = constituent_set.MaterialConstituents or []
    if not constituents:
        return fractions

    # Get quantities and compute fractions based on widths
    total_width_mm = 0.0
    constituent_widths = {}

    for constituent in constituents:
        width_mm = 1.0  # Default width if none found
        constituent_widths[constituent] = width_mm * unit_scale_to_mm
        total_width_mm += width_mm * unit_scale_to_mm

    if total_width_mm == 0.0:
        fractions = {constituent: 1.0 / len(constituents) for constituent in constituents}
    else:
        fractions = {constituent: (width_mm / total_width_mm) 
                    for constituent, width_mm in constituent_widths.items()}

    return fractions

def get_layer_volumes_and_materials(model, element, volumes, unit_scale_to_mm):
    material_layers = []
    # Prefer net volume, fallback to gross volume
    total_volume = volumes["net"] if volumes["net"] is not None else volumes["gross"]
    
    if total_volume is not None:
        # Convert total_volume to mm³ if it isn't already
        total_volume = total_volume * (unit_scale_to_mm ** 3)
    
    if element.HasAssociations:
        for association in element.HasAssociations:
            if association.is_a('IfcRelAssociatesMaterial'):
                material = association.RelatingMaterial

                if material.is_a('IfcMaterialLayerSetUsage'):
                    total_thickness = sum(layer.LayerThickness for layer in material.ForLayerSet.MaterialLayers)
                    for layer in material.ForLayerSet.MaterialLayers:
                        fraction = layer.LayerThickness / total_thickness if total_thickness else 0
                        layer_volume = total_volume * fraction if total_volume else 0
                        material_layers.append({
                            "name": layer.Material.Name if layer.Material else "Unnamed Material",
                            "volume": layer_volume,  # Already in mm³
                            "fraction": fraction
                        })

                elif material.is_a('IfcMaterialConstituentSet'):
                    associated_elements = [element]
                    fractions = compute_constituent_fractions(model, material, associated_elements, unit_scale_to_mm)
                    
                    for constituent in material.MaterialConstituents:
                        fraction = fractions.get(constituent, 1.0 / len(material.MaterialConstituents))
                        material_volume = total_volume * fraction if total_volume else 0
                        material_layers.append({
                            "name": constituent.Material.Name if constituent.Material else "Unnamed Material",
                            "volume": material_volume,  # Already in mm³
                            "fraction": fraction
                        })

    if not material_layers and total_volume is not None:
        materials = ifcopenshell.util.element.get_materials(element)
        if materials:
            material_layers.append({
                "name": materials[0].Name if materials[0].Name else "Unnamed Material",
                "volume": total_volume,  # Already in mm³
                "fraction": 1.0
            })
        else:
            material_layers.append({
                "name": "No Material",
                "volume": total_volume,  # Already in mm³
                "fraction": 1.0
            })

    return material_layers

# Add this function to get common properties
@lru_cache(maxsize=1024)
def get_common_properties(element):
    """Get common properties like LoadBearing and IsExternal from an element."""
    properties = {
        "loadBearing": None,
        "isExternal": None
    }
    
    # Try to get from Pset_<ElementType>Common first
    element_class = element.is_a()[3:]  # Strip 'Ifc' from class name
    pset_name = f"Pset_{element_class}Common"
    
    # Check element's property sets
    for rel in element.IsDefinedBy:
        if rel.is_a('IfcRelDefinesByProperties'):
            pset = rel.RelatingPropertyDefinition
            if pset.is_a('IfcPropertySet'):
                # Check if it's the common property set
                if pset.Name == pset_name or pset.Name == "Pset_ElementCommon":
                    for prop in pset.HasProperties:
                        if prop.Name == "LoadBearing":
                            properties["loadBearing"] = bool(getattr(prop, "NominalValue", None).wrappedValue) if hasattr(prop, "NominalValue") else None
                        elif prop.Name == "IsExternal":
                            properties["isExternal"] = bool(getattr(prop, "NominalValue", None).wrappedValue) if hasattr(prop, "NominalValue") else None
    
    return properties

# Add to existing get_volume_from_basequantities function or create a new function
@lru_cache(maxsize=1024)
def get_area_from_basequantities(element):
    """Get net and gross areas from base quantities."""
    net_area = None
    gross_area = None
    
    for rel_def in element.IsDefinedBy:
        if rel_def.is_a("IfcRelDefinesByProperties"):
            prop_set = rel_def.RelatingPropertyDefinition
            if prop_set.is_a("IfcElementQuantity"):
                for quantity in prop_set.Quantities:
                    # Handle area quantities
                    if quantity.is_a("IfcQuantityArea"):
                        try:
                            if quantity.Name in ["NetArea", "NetSideArea"]:
                                net_area = float(quantity.AreaValue)
                            elif quantity.Name in ["GrossArea", "GrossSideArea"]:
                                gross_area = float(quantity.AreaValue)
                        except (ValueError, AttributeError):
                            continue
    
    return {"net": net_area, "gross": gross_area}

def get_area_from_properties(element):
    """Get net and gross areas from properties."""
    # First try to get areas from BaseQuantities
    areas = get_area_from_basequantities(element)
    if areas["net"] is not None or areas["gross"] is not None:
        return areas

    # If no areas found in BaseQuantities, try properties
    net_area = get_element_property(element, "NetArea") or get_element_property(element, "NetSideArea")
    gross_area = get_element_property(element, "GrossArea") or get_element_property(element, "GrossSideArea")
    
    try:
        net_area = float(net_area) if net_area else None
        gross_area = float(gross_area) if gross_area else None
    except ValueError:
        net_area = None
        gross_area = None

    return {"net": net_area, "gross": gross_area}

# Add to existing get_basequantities function or create a new one
@lru_cache(maxsize=1024)
def get_dimensions_from_basequantities(element):
    """Get length, width, and height from base quantities."""
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

def get_dimensions_from_properties(element):
    """Get length, width, and height from properties."""
    # First try base quantities
    dimensions = get_dimensions_from_basequantities(element)
    if any(dimensions.values()):
        return dimensions

    # Try properties if not found in base quantities
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

# Add this new function to get object type
@lru_cache(maxsize=1024)
def get_object_type(element):
    """Get the object type of an element."""
    object_type = None
    
    # Check IsTypedBy relationships
    if hasattr(element, "IsTypedBy"):
        for rel in element.IsTypedBy:
            if rel.is_a("IfcRelDefinesByType"):
                type_object = rel.RelatingType
                if type_object:
                    # Get the type name
                    object_type = type_object.Name if hasattr(type_object, "Name") else None
                break
    
    return object_type

# Modify the initialization function
def init_ifcopenshell(file_path: str, scale: float):
    """Initialize ifcopenshell in each process"""
    global ifc_file, unit_scale
    try:
        ifc_file = ifcopenshell.open(file_path)
        unit_scale = scale
    except Exception as e:
        logger.error(f"Error initializing process: {str(e)}")
        ifc_file = None
        unit_scale = 1.0

def process_element_parallel(element_id):
    """Process a single element in parallel"""
    try:
        element = ifc_file.by_id(element_id)
        if not element:
            return None

        # Get all properties first
        volumes = get_volume_from_properties(element)
        areas = get_area_from_properties(element)
        dimensions = get_dimensions_from_properties(element)
        materials = get_layer_volumes_and_materials(ifc_file, element, volumes, unit_scale)
        common_props = get_common_properties(element)
        
        # Get basic properties that don't need complex objects
        global_id = element.GlobalId if hasattr(element, 'GlobalId') else None
        element_type = element.is_a()
        element_name = element.Name if hasattr(element, 'Name') else None
        
        # Get predefined type safely
        try:
            predefined_type = getattr(element, "PredefinedType", None)
            if predefined_type:
                if hasattr(predefined_type, "is_a"):
                    if predefined_type.is_a() == "IfcLabel":
                        predefined_type = predefined_type.wrappedValue
                else:
                    predefined_type = str(predefined_type)
        except Exception:
            predefined_type = None
            
        object_type = get_object_type(element)
        
        # Convert measurements to mm
        volume_scale = unit_scale ** 3  # For volumes (m³ to mm³)
        area_scale = unit_scale ** 2    # For areas (m² to mm²)
        
        # Scale volumes
        if volumes["net"] is not None:
            volumes["net"] *= volume_scale
        if volumes["gross"] is not None:
            volumes["gross"] *= volume_scale
            
        # Scale areas
        if areas["net"] is not None:
            areas["net"] *= area_scale
        if areas["gross"] is not None:
            areas["gross"] *= area_scale
            
        # Scale linear dimensions
        if dimensions["length"] is not None:
            dimensions["length"] *= unit_scale
        if dimensions["width"] is not None:
            dimensions["width"] *= unit_scale
        if dimensions["height"] is not None:
            dimensions["height"] *= unit_scale
        
        # Create result dictionary with only serializable data
        return {
            "id": str(element_id),
            "globalId": global_id,
            "type": element_type,
            "predefinedType": predefined_type,
            "objectType": object_type,
            "name": element_name,
            "level": None,
            "volume": volumes["net"] if volumes["net"] is not None else (volumes["gross"] if volumes["gross"] is not None else 0),
            "netVolume": volumes["net"] if volumes["net"] is not None else None,
            "grossVolume": volumes["gross"] if volumes["gross"] is not None else None,
            "netArea": areas["net"],
            "grossArea": areas["gross"],
            "length": dimensions["length"],
            "width": dimensions["width"],
            "height": dimensions["height"],
            "materials": materials,
            "loadBearing": common_props["loadBearing"],
            "isExternal": common_props["isExternal"]
        }
    except Exception as element_error:
        logger.error(f"Error processing element {element_id}: {str(element_error)}")
        return None

# Modify the process_ifc endpoint
@app.post("/api/process-ifc")
async def process_ifc(file: UploadFile = File(...)):
    tmp_file_path = None
    try:
        logger.info(f"Processing file: {file.filename}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file.flush()
            tmp_file_path = tmp_file.name
        
        async def process_and_stream():
            try:
                main_ifc = ifcopenshell.open(tmp_file_path)
                logger.info("IFC file opened successfully")
                
                # Calculate unit scale
                unit_scale = calculate_unit_scale(main_ifc) * 1000.0  # Convert to mm
                logger.info(f"Unit scale factor to mm: {unit_scale}")
                
                building_elements = main_ifc.by_type("IfcBuildingElement")
                total_elements = len(building_elements)
                logger.info(f"Found {total_elements} building elements")
                
                # Get element IDs
                element_ids = [element.id() for element in building_elements]
                chunk_size = 1000
                elements = []
                processed_count = 0
                
                # Use ProcessPoolExecutor
                num_processes = max(multiprocessing.cpu_count() - 1, 1)
                
                with ProcessPoolExecutor(
                    max_workers=num_processes,
                    initializer=init_ifcopenshell,
                    initargs=(tmp_file_path, unit_scale)
                ) as executor:
                    futures = []
                    for i in range(0, total_elements, chunk_size):
                        chunk_ids = element_ids[i:i + chunk_size]
                        future = executor.submit(process_chunk, chunk_ids)
                        futures.append(future)
                    
                    for future in futures:
                        chunk_results = future.result()
                        valid_results = [r for r in chunk_results if r is not None]
                        elements.extend(valid_results)
                        
                        processed_count += chunk_size
                        progress = min(processed_count / total_elements * 100, 100)
                        
                        yield json.dumps({
                            "progress": progress,
                            "processed": min(processed_count, total_elements),
                            "total": total_elements,
                            "status": "processing"
                        }, ensure_ascii=False).strip() + "\n"
                
                yield json.dumps({
                    "progress": 100,
                    "processed": total_elements,
                    "total": total_elements,
                    "status": "complete",
                    "elements": elements
                }, ensure_ascii=False).strip() + "\n"
                
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                yield json.dumps({
                    "status": "error",
                    "error": str(e)
                }, ensure_ascii=False).strip() + "\n"
            finally:
                if tmp_file_path:
                    try:
                        os.unlink(tmp_file_path)
                        logger.info("Temporary file cleaned up")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up temporary file: {str(cleanup_error)}")

        return StreamingResponse(
            process_and_stream(),
            media_type="application/x-ndjson",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def process_chunk(chunk_ids):
    """Process a chunk of elements"""
    results = []
    for element_id in chunk_ids:
        try:
            element = ifc_file.by_id(element_id)
            if element:
                result = process_element_parallel(element_id)
                if result:
                    results.append(result)
        except Exception as e:
            logger.error(f"Error processing element {element_id}: {str(e)}")
    return results

@app.get("/api/elements/{file_id}")
async def get_elements(file_id: str):
    return {"message": "Not implemented yet"} 

# Define unit types
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

def get_project_units(ifc_file: ifcopenshell.file) -> Dict[str, Any]:
    """Get all project units from IFC file"""
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

def convert_unit_value(value: float, from_unit: Dict[str, Any], to_unit: LengthUnit) -> float:
    """Convert value from one unit to another"""
    # First convert to meters (SI base unit)
    if from_unit["name"] == "METRE":
        value_in_meters = value * (10 ** (get_si_prefix_exponent(from_unit.get("prefix"))))
    else:
        # Handle conversion based units (like FOOT, INCH)
        value_in_meters = value * from_unit.get("conversion_factor", 1.0)
    
    # Then convert to target unit
    return convert_from_meters(value_in_meters, to_unit)

def get_si_prefix_exponent(prefix: Optional[str]) -> int:
    """Get the exponent for SI unit prefix"""
    if not prefix:
        return 0
    
    prefix_map = {
        "EXA": 18,
        "PETA": 15,
        "TERA": 12,
        "GIGA": 9,
        "MEGA": 6,
        "KILO": 3,
        "HECTO": 2,
        "DECA": 1,
        "DECI": -1,
        "CENTI": -2,
        "MILLI": -3,
        "MICRO": -6,
        "NANO": -9,
        "PICO": -12,
        "FEMTO": -15,
        "ATTO": -18,
    }
    return prefix_map.get(prefix, 0)

def convert_from_meters(value: float, to_unit: LengthUnit) -> float:
    """Convert value from meters to target unit"""
    conversion_factors = {
        LengthUnit.METER: 1,
        LengthUnit.MILLIMETER: 1000,
        LengthUnit.CENTIMETER: 100,
        LengthUnit.KILOMETER: 0.001,
        LengthUnit.INCH: 39.3701,
        LengthUnit.FOOT: 3.28084,
        LengthUnit.MILE: 0.000621371,
        # Add other conversions as needed
    }
    return value * conversion_factors.get(to_unit, 1) 