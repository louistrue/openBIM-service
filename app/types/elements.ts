export interface Material {
  name: string;
  volume: number;
  fraction: number;
}

export interface IFCElement {
  id: string;
  globalId: string | null;
  type: string;
  predefinedType: string | null;
  objectType: string | null;
  name: string | null;
  level: string | null;
  volume: number;
  netVolume: number | null;
  grossVolume: number | null;
  netArea: number | null;
  grossArea: number | null;
  length: number | null;
  width: number | null;
  height: number | null;
  materials: Material[];
  loadBearing: boolean | null;
  isExternal: boolean | null;
}
