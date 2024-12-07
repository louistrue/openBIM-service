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
                "volume": layer_volume,
                "fraction": fraction
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

    def get_material_volumes(self, element) -> Dict[str, float]:
        """Get material volumes for an element."""
        volumes = get_volume_from_properties(element)
        total_volume = volumes.get("net") or volumes.get("gross") or 0.0
        
        material_volumes = {}
        material_layers = self.get_layer_volumes_and_materials(element, total_volume)
        
        for layer in material_layers:
            material_volumes[layer["name"]] = {
                "volume": layer["volume"],
                "fraction": layer["fraction"]
            }
        
        return material_volumes