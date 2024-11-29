from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import ifcopenshell
import ifcopenshell.geom
import numpy as np
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
import os

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

def process_ifc_file(file_path: Path) -> ProcessedIFC:
    """Process an IFC file and extract geometry data."""
    ifc_file = ifcopenshell.open(str(file_path))
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
            print(f"Error processing element {product.id()}: {e}")
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

@app.post("/api/process-ifc")
async def process_ifc(file: UploadFile) -> ProcessedIFC:
    """Process an uploaded IFC file."""
    if not file.filename.endswith('.ifc'):
        raise HTTPException(400, "File must be an IFC file")
    
    file_path = UPLOAD_DIR / f"{uuid.uuid4()}.ifc"
    try:
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Process file
        result = process_ifc_file(file_path)
        return result
    
    finally:
        if file_path.exists():
            os.unlink(file_path)

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"} 