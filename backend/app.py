from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ifcopenshell
import ifcopenshell.util.element
from ifcopenshell.util.unit import calculate_unit_scale
import tempfile
import os
import logging

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

def get_element_property(element, property_name):
    element_class = element.is_a()[3:]  # Strip 'Ifc' from class name
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

@app.post("/api/process-ifc")
async def process_ifc(file: UploadFile = File(...)):
    tmp_file = None
    try:
        logger.info(f"Processing file: {file.filename}")
        
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.ifc')
        content = await file.read()
        tmp_file.write(content)
        tmp_file.flush()
        
        logger.info(f"Temporary file created: {tmp_file.name}")
        
        try:
            ifc_file = ifcopenshell.open(tmp_file.name)
            logger.info("IFC file opened successfully")
            
            unit_scale_to_mm = calculate_unit_scale(ifc_file) * 1000.0
            
            elements = []
            building_elements = ifc_file.by_type("IfcBuildingElement")
            logger.info(f"Found {len(building_elements)} building elements")
            
            for element in building_elements:
                try:
                    volumes = get_volume_from_properties(element)
                    materials = get_layer_volumes_and_materials(ifc_file, element, volumes, unit_scale_to_mm)

                    element_data = {
                        "id": str(element.id()),
                        "type": element.is_a(),
                        "name": element.Name if hasattr(element, 'Name') else None,
                        "level": None,
                        "volume": volumes["net"] if volumes["net"] is not None else (volumes["gross"] if volumes["gross"] is not None else 0),
                        "netVolume": volumes["net"] if volumes["net"] is not None else None,
                        "grossVolume": volumes["gross"] if volumes["gross"] is not None else None,
                        "materials": materials
                    }
                    elements.append(element_data)
                    
                except Exception as element_error:
                    logger.error(f"Error processing element {element.id()}: {str(element_error)}")
                    continue

            logger.info(f"Successfully processed {len(elements)} elements")
            return {"elements": elements}

        except Exception as ifc_error:
            logger.error(f"Error processing IFC file: {str(ifc_error)}")
            raise HTTPException(status_code=500, detail=f"Error processing IFC file: {str(ifc_error)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if tmp_file:
            try:
                tmp_file.close()
                os.unlink(tmp_file.name)
                logger.info("Temporary file cleaned up")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temporary file: {str(cleanup_error)}")

@app.get("/api/elements/{file_id}")
async def get_elements(file_id: str):
    return {"message": "Not implemented yet"} 