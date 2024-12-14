from typing import Dict, List, Optional
import ifcopenshell
import ifcopenshell.util.element
import logging
from app.services.ifc.quantities import get_volume_from_properties

logger = logging.getLogger(__name__)

class MaterialService:
    def __init__(self, ifc_file: ifcopenshell.file):
        self.ifc_file = ifc_file

    def get_layer_volumes_and_materials(self, element, total_volume: float) -> List[Dict]:
        """Get material layers and their volumes for an element."""
        material_layers = []
        
        if element.HasAssociations:
            for association in element.HasAssociations:
                if association.is_a('IfcRelAssociatesMaterial'):
                    material = association.RelatingMaterial
                    
                    if material.is_a('IfcMaterialLayerSetUsage'):
                        material_layers.extend(
                            self._process_layer_set(material.ForLayerSet, total_volume)
                        )
                    elif material.is_a('IfcMaterialConstituentSet'):
                        material_layers.extend(
                            self._process_constituent_set(material, total_volume)
                        )
                    elif material.is_a('IfcMaterial'):
                        material_layers.append({
                            "name": material.Name,
                            "volume": total_volume,
                            "fraction": 1.0
                        })

        return material_layers

    def _process_layer_set(self, layer_set, total_volume: float) -> List[Dict]:
        """Process IfcMaterialLayerSet."""
        layers = []
        total_thickness = sum(layer.LayerThickness for layer in layer_set.MaterialLayers)
        
        for layer in layer_set.MaterialLayers:
            fraction = layer.LayerThickness / total_thickness if total_thickness else 0
            layer_volume = total_volume * fraction if total_volume else 0
            
            layers.append({
                "name": layer.Material.Name if layer.Material else "Unnamed Material",
                "volume": _round_value(layer_volume, 5),
                "fraction": _round_fraction(fraction),
                "width": _round_value(layer.LayerThickness)
            })
        
        return layers

    def _process_constituent_set(self, constituent_set, total_volume: float) -> List[Dict]:
        """Process IfcMaterialConstituentSet."""
        constituents = []
        total_constituents = len(constituent_set.MaterialConstituents)
        
        if total_constituents == 0:
            return constituents

        # Equal distribution if no specific fractions are defined
        fraction = 1.0 / total_constituents
        
        for constituent in constituent_set.MaterialConstituents:
            constituents.append({
                "name": constituent.Material.Name if constituent.Material else "Unnamed Material",
                "volume": total_volume * fraction if total_volume else 0,
                "fraction": fraction
            })
        
        return constituents

    def get_element_materials(self, element) -> List[str]:
        """Get list of material names for an element."""
        materials = []
        
        if element.HasAssociations:
            for association in element.HasAssociations:
                if association.is_a('IfcRelAssociatesMaterial'):
                    material = association.RelatingMaterial
                    
                    if material.is_a('IfcMaterialLayerSetUsage'):
                        for layer in material.ForLayerSet.MaterialLayers:
                            if layer.Material:
                                materials.append(layer.Material.Name)
                    
                    elif material.is_a('IfcMaterialConstituentSet'):
                        for constituent in material.MaterialConstituents:
                            if constituent.Material:
                                materials.append(constituent.Material.Name)
                    
                    elif material.is_a('IfcMaterial'):
                        materials.append(material.Name)

        return materials

    def get_material_volumes(self, element):
        volumes = get_volume_from_properties(element)
        total_volume = volumes.get("net") or volumes.get("gross") or 0.0
        
        material_layers = self.get_layer_volumes_and_materials(element, total_volume)
        
        # Create material volumes with unique keys for each layer
        material_volumes = {}
        
        # If we have only one material and no layer information, try to get width from element dimensions
        if len(material_layers) == 1 and "width" not in material_layers[0]:
            from app.services.ifc.quantities import get_dimensions_from_properties
            dimensions = get_dimensions_from_properties(element)
            if dimensions and "width" in dimensions:
                material_layers[0]["width"] = dimensions["width"]
        
        # Create a mapping of layer index to unique key
        layer_to_key = {}
        
        for i, layer in enumerate(material_layers):
            material_name = layer["name"]
            # Create unique key for each layer
            key = material_name
            counter = 1
            while key in material_volumes:
                key = f"{material_name} ({counter})"
                counter += 1
            
            # Store mapping of layer index to key
            layer_to_key[i] = key
            
            # Copy all data from layer with rounded values
            material_volumes[key] = {
                "fraction": layer["fraction"],
                "volume": _round_value(layer["volume"], 5)
            }
            
            # Copy width if present
            if "width" in layer:
                material_volumes[key]["width"] = _round_value(layer["width"])
        
        return material_volumes

def _round_value(value: float, digits: int = 3) -> float:
    """Round float value to specified number of digits."""
    if isinstance(value, (int, float)):
        return round(value, digits)
    return value

def _round_fraction(value: float) -> float:
    """Round fraction to 5 digits."""
    return _round_value(value, 5)