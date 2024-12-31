from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import tempfile
import os
import logging
import numpy as np
import uuid
import ifcopenshell
import ifcopenshell.geom

router = APIRouter()
logger = logging.getLogger(__name__)

class Mesh(BaseModel):
    vertices: List[List[float]]
    indices: List[int]
    normals: Optional[List[List[float]]]
    colors: Optional[List[List[float]]]
    material_id: Optional[str]

class ProcessedIFC(BaseModel):
    meshes: List[Mesh]
    bounds: List[List[float]]
    element_count: int

def calculate_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Calculate vertex normals for a mesh."""
    normals = np.zeros_like(vertices)
    
    for face in faces:
        v0, v1, v2 = vertices[face]
        normal = np.cross(v1 - v0, v2 - v0)
        normals[face] += normal
    
    # Normalize
    norms = np.linalg.norm(normals, axis=1)
    norms[norms == 0] = 1
    normals = normals / norms[:, np.newaxis]
    
    return normals

def process_ifc_geometry(file_path: str) -> ProcessedIFC:
    """Process an IFC file and extract geometry data."""
    ifc_file = ifcopenshell.open(file_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    
    meshes: List[Mesh] = []
    min_bounds = np.array([float('inf')] * 3)
    max_bounds = np.array([float('-inf')] * 3)
    
    for product in ifc_file.by_type("IfcProduct"):
        if not product.Representation:
            continue
            
        try:
            # Create shape from product
            shape = ifcopenshell.geom.create_shape(settings, product)
            
            # Get geometry data from shape
            geometry = shape.geometry
            if not geometry:
                continue
                
            # Extract vertices and faces
            verts = np.array(geometry.verts).reshape(-1, 3)
            faces = np.array(geometry.faces).reshape(-1, 3)
            
            # Update bounds
            min_bounds = np.minimum(min_bounds, verts.min(axis=0))
            max_bounds = np.maximum(max_bounds, verts.max(axis=0))
            
            # Calculate normals
            normals = calculate_normals(verts, faces)
            
            meshes.append(Mesh(
                vertices=verts.tolist(),
                indices=faces.flatten().tolist(),
                normals=normals.tolist(),
                colors=None,
                material_id=str(uuid.uuid4())
            ))
        except Exception as e:
            logger.error(f"Error processing element {product.id()}: {e}")
            continue
    
    # Handle case where no valid geometry was found
    if len(meshes) == 0 or np.any(np.isinf(min_bounds)) or np.any(np.isinf(max_bounds)):
        min_bounds = np.zeros(3)
        max_bounds = np.zeros(3)
    
    return ProcessedIFC(
        meshes=meshes,
        bounds=[min_bounds.tolist(), max_bounds.tolist()],
        element_count=len(meshes)
    )

@router.post("/process-geometry",
    summary="Extract 3D Geometry as Mesh Data",
    description="""
    Extracts 3D geometry from an IFC file and converts it into mesh data suitable for rendering.
    Returns vertices, indices (faces), normals, and bounding box information.
    
    Warning: This is a computationally intensive operation, especially for large IFC files.
    
    Output Format:
    ```json
    {
      "meshes": [
        {
          "vertices": [[x1,y1,z1], [x2,y2,z2], ...],  // 3D coordinates
          "indices": [i1,i2,i3, ...],                  // Triangular faces (3 indices per face)
          "normals": [[nx1,ny1,nz1], ...],            // Normal vectors for lighting
          "colors": null,                              // Optional vertex colors
          "material_id": "uuid"                        // Unique identifier for material
        },
        // ... more meshes ...
      ],
      "bounds": [
        [min_x, min_y, min_z],  // Minimum bounds
        [max_x, max_y, max_z]   // Maximum bounds
      ],
      "element_count": 3        // Number of geometric elements
    }
    ```
    
    Technical Details:
    - Vertices: World coordinates in model units
    - Indices: Zero-based indices forming triangular faces
    - Normals: Unit vectors for surface lighting calculations
    - Bounds: Axis-aligned bounding box of entire model
    
    Use Cases:
    - Integration with 3D viewers/engines
    - Custom geometry processing
    - Collision detection
    - Space analysis
    
    Note: Consider using dedicated IFC viewers for visualization only.
    This endpoint is intended for programmatic geometry processing.
    """)
async def process_geometry(file: UploadFile = File(...)) -> ProcessedIFC:
    """Process an IFC file and extract geometry data."""
    if not file.filename.endswith('.ifc'):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be an IFC file.")
        
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        # Process file geometry
        result = process_ifc_geometry(temp_path)
        return result
    
    except Exception as e:
        logger.error(f"Error processing IFC geometry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path) 