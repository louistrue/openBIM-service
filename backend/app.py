from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ifcopenshell
import ifcopenshell.util.element
from ifcopenshell.util.unit import calculate_unit_scale
import tempfile
import os
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import asyncio
from fastapi.responses import StreamingResponse
import json

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
                            "volume": round(layer_volume, 5),
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
                            "volume": round(material_volume, 5),
                            "fraction": fraction
                        })

    if not material_layers:
        materials = ifcopenshell.util.element.get_materials(element)
        if materials:
            material_layers.append({
                "name": materials[0].Name if materials[0].Name else "Unnamed Material",
                "volume": total_volume if total_volume is not None else 0,
                "fraction": 1.0
            })
        else:
            material_layers.append({
                "name": "No Material",
                "volume": total_volume if total_volume is not None else 0,
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

async def process_element(element, ifc_file, unit_scale_to_mm):
    try:
        volumes = get_volume_from_properties(element)
        areas = get_area_from_properties(element)
        dimensions = get_dimensions_from_properties(element)
        materials = get_layer_volumes_and_materials(ifc_file, element, volumes, unit_scale_to_mm)
        common_props = get_common_properties(element)
        
        # Get GlobalId
        global_id = element.GlobalId if hasattr(element, 'GlobalId') else None
        
        # Get predefined type - Fixed error handling
        try:
            predefined_type = getattr(element, "PredefinedType", None)
            if predefined_type:
                if hasattr(predefined_type, "is_a"):
                    if predefined_type.is_a() == "IfcLabel":
                        predefined_type = predefined_type.wrappedValue
                else:
                    # If predefined_type is a string, use it directly
                    predefined_type = str(predefined_type)
        except Exception as type_error:
            logger.debug(f"Could not get predefined type for element {element.id()}: {str(type_error)}")
            predefined_type = None
            
        # Get object type
        object_type = get_object_type(element)
        
        return {
            "id": str(element.id()),
            "globalId": global_id,
            "type": element.is_a(),
            "predefinedType": predefined_type,
            "objectType": object_type,
            "name": element.Name if hasattr(element, 'Name') else None,
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
        logger.error(f"Error processing element {element.id()}: {str(element_error)}")
        return None

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
                ifc_file = ifcopenshell.open(tmp_file_path)
                logger.info("IFC file opened successfully")
                
                unit_scale_to_mm = calculate_unit_scale(ifc_file) * 1000.0
                building_elements = ifc_file.by_type("IfcBuildingElement")
                total_elements = len(building_elements)
                logger.info(f"Found {total_elements} building elements")
                
                # Send initial status
                yield json.dumps({
                    "progress": 0,
                    "processed": 0,
                    "total": total_elements,
                    "status": "processing"
                }) + "\n"
                
                chunk_size = 500
                elements = []
                processed_count = 0
                
                for i in range(0, total_elements, chunk_size):
                    chunk = building_elements[i:i + chunk_size]
                    tasks = [
                        process_element(element, ifc_file, unit_scale_to_mm)
                        for element in chunk
                    ]
                    chunk_results = await asyncio.gather(*tasks)
                    valid_results = [e for e in chunk_results if e is not None]
                    elements.extend(valid_results)
                    
                    processed_count += len(chunk)
                    progress = min(processed_count / total_elements * 100, 100)
                    
                    # Send progress update with explicit newline
                    yield json.dumps({
                        "progress": progress,
                        "processed": processed_count,
                        "total": total_elements,
                        "status": "processing"
                    }, ensure_ascii=False).strip() + "\n"
                    
                    # Reduced delay
                    await asyncio.sleep(0.05)  # Reduced from 0.1 to 0.05
                
                # Send final result with explicit newline
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

@app.get("/api/elements/{file_id}")
async def get_elements(file_id: str):
    return {"message": "Not implemented yet"} 