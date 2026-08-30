import type { ThemePreset } from "@/components/sympose"
import type { VaultNode } from "@/components/sympose"

/** The five shipped presets — UI_DESIGN_REFERENCE.md §3.1. */
export const THEME_PRESETS: ThemePreset[] = [
  {
    name: "Obsidian Matte",
    mode: "dark · 0rem · Phosphor",
    swatches: ["#0A0F1D", "#C6D0E0", "#38BDF8", "#34D399", "#C084FC"],
  },
  {
    name: "Blueprint & Paper",
    mode: "light · Lucide",
    swatches: ["#F9F7F1", "#2B2B2B", "#1E4FD8", "#7A3FBF", "#8A6D00"],
  },
  {
    name: "Nordic Spruce",
    mode: "balanced dark",
    swatches: ["#1A2421", "#DDE6E1", "#7EC7A2", "#B8C7A8", "#E3C9A0"],
  },
  {
    name: "Swiss Grid",
    mode: "minimal · sharp",
    swatches: ["#FFFFFF", "#111111", "#E4002B", "#0057B8", "#FFD100"],
  },
  {
    name: "Custom Studio",
    mode: "either · live pickers",
    swatches: ["#12121A", "#EDEDED", "#5CE0C6", "#F59E0B", "#EC4899"],
  },
]

/** Mock vault — UI_DESIGN_REFERENCE.md §9, plus system folders to prove they filter. */
export const MOCK_VAULT: VaultNode[] = [
  {
    name: "Projects",
    path: "Projects",
    type: "folder",
    children: [
      {
        name: "Sympose",
        path: "Projects/Sympose",
        type: "folder",
        children: [
          { name: "Architecture.md", path: "Projects/Sympose/Architecture.md", type: "note" },
          { name: "Roadmap.md", path: "Projects/Sympose/Roadmap.md", type: "note" },
          { name: "Dashboard-UI.md", path: "Projects/Sympose/Dashboard-UI.md", type: "note" },
        ],
      },
    ],
  },
  { name: "General", path: "General", type: "folder", children: [] },
  {
    name: "Thoughts",
    path: "Thoughts",
    type: "folder",
    children: [
      { name: "creativity.md", path: "Thoughts/creativity.md", type: "note" },
    ],
  },
  {
    name: "Daily",
    path: "Daily",
    type: "folder",
    children: [
      {
        name: "2026",
        path: "Daily/2026",
        type: "folder",
        children: [
          {
            name: "08-August",
            path: "Daily/2026/08-August",
            type: "folder",
            children: [
              { name: "2026-08-29.md", path: "Daily/2026/08-August/2026-08-29.md", type: "note" },
              { name: "2026-08-30.md", path: "Daily/2026/08-August/2026-08-30.md", type: "note" },
            ],
          },
        ],
      },
    ],
  },
  { name: "Templates", path: "Templates", type: "folder", children: [] },
  {
    name: ".obsidian",
    path: ".obsidian",
    type: "folder",
    children: [{ name: "workspace.json", path: ".obsidian/workspace.json", type: "note" }],
  },
  { name: ".trash", path: ".trash", type: "folder", children: [] },
]
