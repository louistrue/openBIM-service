export interface Material {
  name: string;
  volume: number;
  fraction: number;
}

export interface IFCElement {
  id: string;
  type: string;
  name?: string;
  level?: string;
  volume: number;
  netVolume: number | null;
  grossVolume: number | null;
  materials: Material[];
}
