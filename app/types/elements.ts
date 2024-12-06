export interface IFCElement {
  id: string;
  type: string;
  name?: string;
  level?: string;
  properties?: Record<string, any>;
}
