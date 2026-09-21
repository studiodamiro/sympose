import {
  BookOpen01Icon,
  Calendar03Icon,
  ChefHatIcon,
  Copy01Icon,
  Folder01Icon,
  FolderLibraryIcon,
  FilmRoll01Icon,
  HourglassIcon,
  PaintBrush02Icon,
  PencilEdit02Icon,
  QuoteDownIcon,
  SourceCodeIcon,
  UserMultiple02Icon,
} from "@hugeicons/core-free-icons"
import type { IconSvgElement } from "@hugeicons/react"

/**
 * Curated folder-name → icon map, used only to give a recognized top-level
 * folder a specific glyph instead of the generic folder icon (see
 * `menuIconFor` in `app-shell.tsx`) — not a fixed list of folders every
 * vault must have. A folder name not in this list still works fine, just
 * with the generic icon.
 */
export interface VaultFolder {
  /** Folder name — also the route id and vault-relative path. */
  name: string
  icon: IconSvgElement
}

export const VAULT_FOLDERS: VaultFolder[] = [
  { name: "Projects", icon: FolderLibraryIcon },
  { name: "Code", icon: SourceCodeIcon },
  { name: "Daily", icon: Calendar03Icon },
  { name: "Drawings", icon: PaintBrush02Icon },
  { name: "General", icon: Folder01Icon },
  { name: "Limbo", icon: HourglassIcon },
  { name: "Movies", icon: FilmRoll01Icon },
  { name: "People", icon: UserMultiple02Icon },
  { name: "Quotes", icon: QuoteDownIcon },
  { name: "Reading", icon: BookOpen01Icon },
  { name: "Recipes", icon: ChefHatIcon },
  { name: "Templates", icon: Copy01Icon },
  { name: "Writing", icon: PencilEdit02Icon },
]
