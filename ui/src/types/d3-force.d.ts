declare module "d3-force" {
  // Minimal ambient stub — this package ships no types of its own. Only
  // `forceRadial(...).strength(...)` is actually called from src (2D
  // nebula); the rest are declared for parity with d3-force-3d, in case
  // the 2D nebula grows the same force-tuning knobs the 3D one has.
  export interface Force {
    (alpha: number): void
    strength(strength: number): Force
  }
  export function forceRadial(radius?: number, x?: number, y?: number): Force
  export function forceCenter(x?: number, y?: number): Force
  export function forceManyBody(): Force
  export function forceLink(): Force
  export function forceX(x?: number): Force
  export function forceY(y?: number): Force
  export function forceCollide(radius?: number): Force
  export function forceSimulation(nodes?: unknown[]): unknown
}
