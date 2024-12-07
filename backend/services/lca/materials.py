from typing import Dict, List, Optional
import ifcopenshell
import ifcopenshell.util.element
import logging

logger = logging.getLogger(__name__)

class MaterialService:
    def __init__(self, ifc_file: ifcopenshell.file):
        self.ifc_file = ifc_file

    def get_layer_volumes_and_materials(self, element, volumes: Dict, unit_scale_to_mm: float) -> List[Dict]:
        """Get material layers and their volumes for an element."""
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
                        material_layers.extend(
                            self._process_layer_set(material, total_volume)
                        )
                    elif material.is_a('IfcMaterialConstituentSet'):
                        material_layers.extend(
                            self._process_constituent_set(
                                material, element, total_volume, unit_scale_to_mm
                            )
                        )

        if not material_layers and total_volume is not None:
            material_layers.extend(
                self._process_single_material(element, total_volume)
            )

        return material_layers

    def _process_layer_set(self, material, total_volume: float) -> List[Dict]:
        """Process IfcMaterialLayerSet."""
        layers = []
        total_thickness = sum(layer.LayerThickness for layer in material.ForLayerSet.MaterialLayers)
        
        for layer in material.ForLayerSet.MaterialLayers:
            fraction = layer.LayerThickness / total_thickness if total_thickness else 0
            layer_volume = total_volume * fraction if total_volume else 0
            
            layers.append({
                "name": layer.Material.Name if layer.Material else "Unnamed Material",
                "volume": layer_volume,  # Already in mm³
                "fraction": fraction
            })
        
        return layers

    def _process_constituent_set(
        self, material, element, total_volume: float, unit_scale_to_mm: float
    ) -> List[Dict]:
        """Process IfcMaterialConstituentSet."""
        constituents = []
        fractions = self._compute_constituent_fractions(
            material, [element], unit_scale_to_mm
        )
        
        for constituent in material.MaterialConstituents:
            fraction = fractions.get(constituent, 1.0 / len(material.MaterialConstituents))
            material_volume = total_volume * fraction if total_volume else 0
            
            constituents.append({
                "name": constituent.Material.Name if constituent.Material else "Unnamed Material",
                "volume": material_volume,  # Already in mm³
                "fraction": fraction
            })
        
        return constituents

    def _process_single_material(self, element, total_volume: float) -> List[Dict]:
        """Process single material assignment."""
        materials = ifcopenshell.util.element.get_materials(element)
        
        if materials:
            return [{
                "name": materials[0].Name if materials[0].Name else "Unnamed Material",
                "volume": total_volume,  # Already in mm³
                "fraction": 1.0
            }]
        
        return [{
            "name": "No Material",
            "volume": total_volume,  # Already in mm³
            "fraction": 1.0
        }]

    def _compute_constituent_fractions(
        self, constituent_set, associated_elements, unit_scale_to_mm: float
    ) -> Dict:
        """Compute volume fractions for material constituents."""
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
            fractions = {
                constituent: (width_mm / total_width_mm) 
                for constituent, width_mm in constituent_widths.items()
            }

        return fractions 