import os
import logging
import ifcopenshell
from pathlib import Path
from typing import Union, List, Dict
import tempfile
from shutil import copyfile
import traceback

logger = logging.getLogger(__name__)

class StoreySpiltterService:
    def __init__(self, ifc_file: ifcopenshell.file):
        self.file = ifc_file

    def split_by_storey(self, output_dir: Union[str, None] = None) -> List[Dict[str, str]]:
        """Split an IFC model into multiple models based on building storey."""
        src_path = None
        try:
            if output_dir is None:
                output_dir = tempfile.mkdtemp()
            else:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

            # Create temporary file for the source
            with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as temp_file:
                src_path = temp_file.name
                logger.info(f"Writing source file to {src_path}")
                self.file.write(src_path)

            result_files = []
            storeys = self.file.by_type("IfcBuildingStorey")
            logger.info(f"Found {len(storeys)} storeys")
            
            if not storeys:
                logger.warning("No storeys found in the IFC file")
                raise ValueError("No storeys found in the IFC file")
            
            for i, storey in enumerate(storeys):
                try:
                    filename = f"{i}-{storey.Name if storey.Name else 'Unnamed'}.ifc"
                    dest_path = os.path.join(output_dir, filename)
                    logger.info(f"Processing storey {i}: {storey.Name} -> {dest_path}")
                    
                    # Create the split file
                    copyfile(src_path, dest_path)
                    old_ifc = ifcopenshell.open(dest_path)
                    new_ifc = ifcopenshell.file(schema=self.file.schema)

                    # Process elements
                    if self.file.schema == "IFC2X3":
                        elements = old_ifc.by_type("IfcProject") + old_ifc.by_type("IfcProduct")
                    else:
                        elements = old_ifc.by_type("IfcContext") + old_ifc.by_type("IfcProduct")

                    # Add elements and their relationships
                    inverse_elements = []
                    for element in elements:
                        try:
                            if element.is_a("IfcElement") and not self._is_in_storey(element, storey):
                                element.Representation = None
                                continue
                            if element.is_a("IfcElement"):
                                styled_rep_items = [
                                    i for i in old_ifc.traverse(element) 
                                    if i.is_a("IfcRepresentationItem") and i.StyledByItem
                                ]
                                for item in styled_rep_items:
                                    if item.StyledByItem:
                                        new_ifc.add(item.StyledByItem[0])
                            new_ifc.add(element)
                            inverse_elements.extend(old_ifc.get_inverse(element))
                        except Exception as elem_error:
                            logger.error(f"Error processing element {element.id()}: {str(elem_error)}")
                            continue

                    for inverse_element in inverse_elements:
                        try:
                            new_ifc.add(inverse_element)
                        except Exception as inv_error:
                            logger.error(f"Error adding inverse element: {str(inv_error)}")
                            continue

                    # Remove elements not in this storey
                    for element in new_ifc.by_type("IfcElement"):
                        if not self._is_in_storey(element, storey):
                            new_ifc.remove(element)

                    # Save the file
                    new_ifc.write(dest_path)
                    
                    # Add to results
                    result_files.append({
                        "storey_name": storey.Name if storey.Name else "Unnamed",
                        "storey_id": storey.GlobalId,
                        "file_path": dest_path,
                        "file_name": filename
                    })

                except Exception as storey_error:
                    logger.error(f"Error processing storey {i}: {str(storey_error)}")
                    continue

            return result_files, output_dir

        except Exception as e:
            logger.error(f"Error in split_by_storey: {str(e)}\n{traceback.format_exc()}")
            if output_dir and os.path.exists(output_dir):
                shutil.rmtree(output_dir)
            raise

        finally:
            if src_path and os.path.exists(src_path):
                os.unlink(src_path)

    def _is_in_storey(self, element: ifcopenshell.entity_instance, storey: ifcopenshell.entity_instance) -> bool:
        """Check if an element is contained in a specific storey."""
        try:
            return (
                (contained_in_structure := element.ContainedInStructure)
                and (relating_structure := contained_in_structure[0].RelatingStructure).is_a("IfcBuildingStorey")
                and relating_structure.GlobalId == storey.GlobalId
            )
        except Exception:
            return False