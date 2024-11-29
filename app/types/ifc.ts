export interface Mesh {
  vertices: number[][];
  indices: number[];
  normals: number[][];
  colors?: number[][];
  material_id?: string;
}

export interface ProcessedIFC {
  meshes: Mesh[];
  bounds: number[][];
  element_count: number;
}
