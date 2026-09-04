declare module "d3-force" {
  export function forceRadial(radius?: number, x?: number, y?: number): any
  export function forceCenter(x?: number, y?: number): any
  export function forceManyBody(): any
  export function forceLink(): any
  export function forceX(x?: number): any
  export function forceY(y?: number): any
  export function forceCollide(radius?: number): any
  export function forceSimulation(nodes?: any[]): any
}
