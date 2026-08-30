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
 * Top-level folders of the Sympose Obsidian vault, in display order. These are
 * real vault directories (UI_DESIGN_REFERENCE.md §6.8e) surfaced as the main-menu
 * destinations. Icons are chosen to read from the folder name at a glance rather
 * than the generic folder glyph.
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
