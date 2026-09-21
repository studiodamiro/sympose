declare module "d3-force-3d" {
  // Minimal ambient stub — this package ships no types of its own. Only
  // `forceRadial(...).strength(...)` is actually called from src (3D
  // nebula, adding the `z` axis 2D's d3-force lacks).
  export interface Force {
    (alpha: number): void
    strength(strength: number): Force
  }
  export function forceRadial(
    radius?: number,
    x?: number,
    y?: number,
    z?: number
  ): Force
  export function forceCenter(x?: number, y?: number, z?: number): Force
  export function forceManyBody(): Force
  export function forceLink(): Force
  export function forceX(x?: number): Force
  export function forceY(y?: number): Force
  export function forceZ(z?: number): Force
}
