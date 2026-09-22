export { ActionBadge } from "./action-badge"
export { ChatActionGroup } from "./chat-action-group"
export { ChatMessage, StreamingCaret } from "./chat-message"
export { ChatPanel } from "./chat-panel"
export { ConfirmDialog } from "./confirm-dialog"
export { ContentPanel } from "./content-panel"
export {
  ControlRow,
  ControlSection,
  ControlSectionsProvider,
  useCollapseAll,
  CollapseAllButton,
} from "./control-section"
export { EditorPreferencesSection } from "./editor-preferences-section"
export { FrontmatterCard } from "./frontmatter-card"
// `AmbientNebula` is intentionally NOT re-exported here — it pulls in
// `react-force-graph`. The app shell lazy-imports it directly from
// "@/components/sympose/ambient-nebula" so it stays off the TTFT hot path.
export {
  MainMenu,
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  MENU_TRASH_ID,
  type MainMenuItem,
} from "./main-menu"
export { MarkdownPanel, TOOLBAR_ICONS } from "./markdown-panel"
export { NebulaAppearanceSection } from "./nebula-appearance-section"
export { NebulaModeToggle } from "./nebula-mode-toggle"
export { NotificationsSection } from "./notifications-section"
export { ModelChip } from "./model-chip"
export { PersonaCard } from "./persona-card"
export {
  RecentNotesPreferencesSection,
} from "./recent-notes-preferences-section"
export {
  SegmentedControl,
  type SegmentedControlOption,
} from "./segmented-control"
export { ThemeToggle } from "./theme-toggle"
export { TopBar } from "./top-bar"
export { TrashList } from "./trash-list"
export { WorkspaceSection } from "./workspace-section"
export { WorkspaceSwitcher } from "./workspace-switcher"
export {
  filterVaultTree,
  filterTreeByQuery,
  flatSearchTree,
  collectFolderPaths,
  VaultTree,
  type VaultNode,
  type FlatVaultMatch,
} from "./vault-tree"
