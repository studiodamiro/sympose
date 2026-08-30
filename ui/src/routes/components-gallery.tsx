import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  FilterIcon,
  SlidersHorizontalIcon,
  Search01Icon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { PERSONA_LIST } from "@/lib/personas"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

import {
  ActionBadge,
  type ActionKind,
  CapacityMeter,
  ChatMessage,
  Composer,
  ControlRow,
  ControlSection,
  EntityPath,
  MetaText,
  ModelChip,
  Panel,
  PanelContent,
  PanelFooter,
  PanelHeader,
  PanelTitle,
  PersonaPill,
  PresetCard,
  QuietToggle,
  SegmentedControl,
  StatusBar,
  StatusTag,
  VaultTree,
  WikiLink,
} from "@/components/sympose"
import { THEME_PRESETS, MOCK_VAULT } from "@/routes/gallery-data"

/* ------------------------------------------------------------------ layout -- */

interface Section {
  id: string
  title: string
}

const SECTIONS: Section[] = [
  { id: "foundations", title: "Foundations" },
  { id: "persona", title: "Persona identity" },
  { id: "chat", title: "Multi-agent chat" },
  { id: "vault", title: "Vault explorer" },
  { id: "nebula", title: "Nebula controls" },
  { id: "settings", title: "Settings" },
  { id: "status", title: "Status & runtime" },
  { id: "primitives", title: "shadcn primitives" },
]

function GallerySection({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-border py-10 first:border-t-0">
      <h2 className="font-heading text-xl font-semibold text-fg-strong">
        {title}
      </h2>
      {description && (
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          {description}
        </p>
      )}
      <div className="mt-6 flex flex-col gap-8">{children}</div>
    </section>
  )
}

function Row({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="font-mono text-xs text-fg-muted">{label}</span>
      <div className={cn("flex flex-wrap items-center gap-3", className)}>
        {children}
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- gallery -- */

const ACTION_KINDS: { kind: ActionKind; detail?: string }[] = [
  { kind: "WRITE_NOTE", detail: "Projects/Sympose/Architecture.md" },
  { kind: "APPEND_NOTE", detail: "Daily/2026/08-August/2026-08-30.md" },
  { kind: "DAILY_NOTE", detail: "2026-08-30" },
  { kind: "SEARCH", detail: "self-signed cert fastapi" },
  { kind: "SPAWN_WORKER", detail: "draft ADR-065" },
  { kind: "CONFIG_SET", detail: "runtime.streaming = true" },
  { kind: "CREATE_PERSONA", detail: "@grace" },
  { kind: "DELETE_PERSONA", detail: "@kepler" },
]

export function ComponentsGallery() {
  const [nebulaMode, setNebulaMode] = React.useState<"2d" | "3d">("3d")
  const [interaction, setInteraction] = React.useState<"explore" | "focus">(
    "focus"
  )
  const [preset, setPreset] = React.useState(THEME_PRESETS[0].name)
  const [selectedNote, setSelectedNote] = React.useState<string>()

  return (
    <div className="mx-auto flex max-w-6xl gap-10 px-6 py-8">
      {/* TOC */}
      <aside className="sticky top-20 hidden h-fit w-44 shrink-0 flex-col gap-1 text-sm lg:flex">
        <span className="mb-1 font-mono text-xs text-fg-muted">ON THIS PAGE</span>
        {SECTIONS.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            className="py-1 text-muted-foreground transition-colors hover:text-brand"
          >
            {s.title}
          </a>
        ))}
      </aside>

      <div className="min-w-0 flex-1">
        <header className="pb-4">
          <h1 className="font-heading text-2xl font-semibold text-fg-strong">
            Sympose component library
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            shadcn/ui primitives (base-maia) plus the Sympose-specific molecules
            from{" "}
            <span className="font-mono text-entity">
              docs/UI_DESIGN_REFERENCE.md
            </span>
            . Every custom component is built on shadcn principles — {" "}
            <span className="font-mono text-xs">cva</span> variants,{" "}
            <span className="font-mono text-xs">cn()</span>, {" "}
            <span className="font-mono text-xs">data-slot</span> hooks, semantic
            tokens.
          </p>
        </header>

        {/* ---------------------------------------------------- foundations -- */}
        <GallerySection
          id="foundations"
          title="Foundations"
          description="Semantic accent tokens layered on top of the base-maia / zinc preset. Utilities: text-brand, bg-ok, border-danger, text-entity, bg-chip, text-fg-muted."
        >
          <Row label="semantic tokens">
            {[
              ["brand", "bg-brand"],
              ["ok", "bg-ok"],
              ["danger", "bg-danger"],
              ["entity", "bg-entity"],
              ["chip", "bg-chip"],
              ["fg-muted", "bg-fg-muted"],
              ["fg-strong", "bg-fg-strong"],
            ].map(([name, bg]) => (
              <div key={name} className="flex flex-col items-center gap-1.5">
                <div className={cn("size-14 border border-border", bg)} />
                <span className="font-mono text-[11px] text-fg-muted">
                  {name}
                </span>
              </div>
            ))}
          </Row>
          <Row label="typography">
            <div className="flex flex-col gap-1">
              <span className="font-heading text-2xl text-fg-strong">
                Engine first, face second
              </span>
              <span className="text-sm text-foreground">
                Body — highly legible sans at 14px, 1.6 leading.
              </span>
              <span className="font-mono text-xs text-fg-muted">
                mono — file paths, ms readouts, YAML frontmatter
              </span>
            </div>
          </Row>
        </GallerySection>

        {/* -------------------------------------------------------- persona -- */}
        <GallerySection
          id="persona"
          title="Persona identity"
          description="Stable accent + icon per persona (§8). PersonaPill leads every chat turn; ModelChip shows the muted backend family and an on-device marker for local models."
        >
          <Row label="<PersonaPill />">
            {PERSONA_LIST.map((p) => (
              <PersonaPill key={p.handle} handle={p.handle} />
            ))}
            <PersonaPill handle="samantha" tone="solid" />
            <PersonaPill handle="grace" size="sm" />
          </Row>
          <Row label="<ModelChip />">
            {PERSONA_LIST.map((p) => (
              <ModelChip key={p.handle} handle={p.handle} />
            ))}
            <ModelChip model="gpt-4o" tier="cloud" />
          </Row>
          <Row label="identity header (composed)">
            <div className="flex items-center gap-2">
              <PersonaPill handle="grace" size="sm" />
              <ModelChip handle="grace" />
              <MetaText>0.42s · 128 tok</MetaText>
            </div>
          </Row>
        </GallerySection>

        {/* ----------------------------------------------------------- chat -- */}
        <GallerySection
          id="chat"
          title="Multi-agent chat"
          description="Turns distinguished by alignment + fill, not chat-bubble kitsch (§7). Action badges render inline under the message that produced them."
        >
          <div className="flex max-w-2xl flex-col gap-5 rounded-lg border border-border bg-card p-5">
            <ChatMessage role="user" timestamp="14:02">
              Good. Draft the ADR and link it from the journal.
            </ChatMessage>
            <ChatMessage
              role="persona"
              handle="grace"
              latency={"<2ms"}
              timestamp="14:02"
              footer={
                <ActionBadge
                  action="WRITE_NOTE"
                  detail="Projects/Sympose/Architecture.md"
                />
              }
            >
              Inverted index verified — backlink lookup at &lt;2ms across the
              current vault.
            </ChatMessage>
            <ChatMessage role="persona" handle="samantha" streaming>
              Formulating the auth plan — shared-password guard plus an in-process
              self-signed cert
            </ChatMessage>
          </div>

          <Row label="<ActionBadge /> — all kinds">
            {ACTION_KINDS.map(({ kind, detail }) => (
              <ActionBadge key={kind} action={kind} detail={detail} />
            ))}
          </Row>

          <div className="max-w-2xl">
            <span className="font-mono text-xs text-fg-muted">
              &lt;Composer /&gt;
            </span>
            <div className="mt-2.5 flex flex-col gap-4">
              <Composer hint="@ to mention · ⌘↵ to send" onSend={() => {}} />
              <Composer disabled hint="Chat endpoint not wired yet" />
            </div>
          </div>
        </GallerySection>

        {/* ---------------------------------------------------------- vault -- */}
        <GallerySection
          id="vault"
          title="Vault explorer"
          description="Sandbox-aware directory tree (system folders filtered), entity-accented paths and wikilinks with an open / centre-in-nebula affordance (§6.5)."
        >
          <div className="flex flex-wrap gap-6">
            <Panel className="w-64">
              <PanelHeader>
                <PanelTitle>vault</PanelTitle>
                <StatusTag status="ok">synced</StatusTag>
              </PanelHeader>
              <PanelContent className="max-h-80">
                <VaultTree
                  nodes={MOCK_VAULT}
                  defaultExpanded={["Projects", "Projects/Sympose", "Daily"]}
                  selectedPath={selectedNote}
                  onSelect={(n) => setSelectedNote(n.path)}
                />
              </PanelContent>
            </Panel>

            <div className="flex flex-1 flex-col gap-4">
              <Row label="<WikiLink />">
                <p className="text-sm leading-relaxed">
                  See <WikiLink target="OAuth" /> and{" "}
                  <WikiLink target="Projects/Sympose/Architecture" label="the ADR" />{" "}
                  — the <WikiLink target="Kepler" unresolved /> note does not exist
                  yet.
                </p>
              </Row>
              <Row label="<EntityPath />">
                <EntityPath path="Projects/Sympose/Architecture.md" />
                <EntityPath
                  path="Daily/2026/08-August/2026-08-30.md"
                  emphasizeLeaf={false}
                />
              </Row>
              <Row label="selected">
                <MetaText>{selectedNote ?? "— nothing selected —"}</MetaText>
              </Row>
            </div>
          </div>
        </GallerySection>

        {/* --------------------------------------------------------- nebula -- */}
        <GallerySection
          id="nebula"
          title="Nebula controls"
          description="Obsidian-parity graph control stack (§6.3): collapsible Filters / Groups / Display / Forces sections, plus the 2D|3D and Explore|Focus segmented switches."
        >
          <div className="flex flex-wrap gap-6">
            <Panel className="w-72">
              <PanelHeader>
                <PanelTitle>nebula</PanelTitle>
                <StatusTag status="stub">graph TODO</StatusTag>
              </PanelHeader>
              <PanelContent className="px-3">
                <ControlSection
                  title="Filters"
                  defaultOpen
                  icon={<HugeiconsIcon icon={FilterIcon} />}
                >
                  <div className="relative">
                    <HugeiconsIcon
                      icon={Search01Icon}
                      className="pointer-events-none absolute top-2 left-2 size-3.5 text-fg-muted"
                    />
                    <Input
                      placeholder="Search files…"
                      className="h-8 pl-7 text-xs"
                    />
                  </div>
                  <ControlRow label="Tags">
                    <Switch defaultChecked />
                  </ControlRow>
                  <ControlRow label="Attachments">
                    <Switch />
                  </ControlRow>
                  <ControlRow label="Existing files only">
                    <Switch defaultChecked />
                  </ControlRow>
                  <ControlRow label="Orphans">
                    <Switch />
                  </ControlRow>
                </ControlSection>
                <ControlSection
                  title="Forces"
                  icon={<HugeiconsIcon icon={SlidersHorizontalIcon} />}
                >
                  {["Center force", "Repel force", "Link force", "Link distance"].map(
                    (l) => (
                      <div key={l} className="flex flex-col gap-1.5">
                        <span className="text-xs text-muted-foreground">{l}</span>
                        <Slider defaultValue={[45]} />
                      </div>
                    )
                  )}
                </ControlSection>
                <ControlSection title="Display">
                  <ControlRow label="Arrows">
                    <Switch />
                  </ControlRow>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs text-muted-foreground">
                      Node size
                    </span>
                    <Slider defaultValue={[60]} />
                  </div>
                </ControlSection>
              </PanelContent>
              <PanelFooter className="justify-between">
                <SegmentedControl
                  aria-label="Nebula render mode"
                  size="sm"
                  value={nebulaMode}
                  onValueChange={setNebulaMode}
                  options={[
                    { value: "2d", label: "2D" },
                    { value: "3d", label: "3D" },
                  ]}
                />
                <QuietToggle>⚙ settings</QuietToggle>
              </PanelFooter>
            </Panel>

            <div className="flex flex-col gap-4">
              <Row label="<SegmentedControl />">
                <SegmentedControl
                  aria-label="Interaction state"
                  value={interaction}
                  onValueChange={setInteraction}
                  options={[
                    { value: "explore", label: "Explore" },
                    { value: "focus", label: "Focus" },
                  ]}
                />
              </Row>
              <Row label="state">
                <MetaText>
                  {nebulaMode.toUpperCase()} · {interaction}
                </MetaText>
              </Row>
            </div>
          </div>
        </GallerySection>

        {/* ------------------------------------------------------- settings -- */}
        <GallerySection
          id="settings"
          title="Settings — Appearance"
          description="Replaces the old theme bar (§6.4). Preset gallery, plus the Shared Memory Compactor capacity meter."
        >
          <Row label="<PresetCard />" className="grid! grid-cols-2 gap-3 sm:grid-cols-3">
            {THEME_PRESETS.map((p) => (
              <PresetCard
                key={p.name}
                preset={p}
                selected={preset === p.name}
                onClick={() => setPreset(p.name)}
              />
            ))}
          </Row>
          <div className="max-w-sm">
            <span className="font-mono text-xs text-fg-muted">
              &lt;CapacityMeter /&gt; — Shared Memory Compactor
            </span>
            <div className="mt-2.5 flex flex-col gap-4">
              <CapacityMeter used={12} total={25} />
              <CapacityMeter used={19} total={25} />
              <CapacityMeter used={24} total={25} />
            </div>
          </div>
        </GallerySection>

        {/* --------------------------------------------------------- status -- */}
        <GallerySection
          id="status"
          title="Status & runtime"
          description="Endpoint status pills, the bottom runtime readout, muted metadata, and the quiet panel-corner toggle."
        >
          <Row label="<StatusTag />">
            <StatusTag status="ok">/health 200</StatusTag>
            <StatusTag status="loading">connecting…</StatusTag>
            <StatusTag status="error">model unreachable</StatusTag>
            <StatusTag status="stub">tree endpoint TODO</StatusTag>
          </Row>
          <Row label="<QuietToggle />">
            <QuietToggle>☀ / 🌙</QuietToggle>
            <QuietToggle active>2D | 3D</QuietToggle>
            <QuietToggle disabled>⚙ settings</QuietToggle>
          </Row>
          <Row label="<MetaText />">
            <MetaText>14:02:19</MetaText>
            <MetaText>1,284 tokens</MetaText>
            <MetaText>&lt;2ms</MetaText>
          </Row>
          <div>
            <span className="font-mono text-xs text-fg-muted">
              &lt;StatusBar /&gt;
            </span>
            <div className="mt-2.5 overflow-hidden rounded-lg border border-border">
              <StatusBar
                items={[
                  { label: "version", value: "0.2.24" },
                  { label: "default persona", value: "samantha" },
                  { label: "personas", value: "3" },
                ]}
                links={[
                  { label: "/docs", href: "/docs" },
                  { label: "/health", href: "/health" },
                ]}
              />
            </div>
          </div>
        </GallerySection>

        {/* ----------------------------------------------------- primitives -- */}
        <GallerySection
          id="primitives"
          title="shadcn primitives (base-maia)"
          description="The unmodified registry components the molecules are built from."
        >
          <Row label="Button">
            <Button>Default</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
          </Row>
          <Row label="Badge">
            <Badge>Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="outline">Outline</Badge>
            <Badge variant="destructive">Destructive</Badge>
          </Row>
          <Row label="Input · Select · Switch">
            <div className="grid w-full max-w-sm gap-2">
              <Label htmlFor="g-in">Daily notes directory</Label>
              <Input id="g-in" defaultValue="Daily/" />
            </div>
            <Select defaultValue="maia">
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["nova", "maia", "sera", "new-york"].map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Switch defaultChecked />
          </Row>
          <Row label="Tabs">
            <Tabs defaultValue="read" className="w-full max-w-md">
              <TabsList>
                <TabsTrigger value="read">Read</TabsTrigger>
                <TabsTrigger value="edit">Edit</TabsTrigger>
              </TabsList>
              <TabsContent value="read" className="pt-3 text-sm text-muted-foreground">
                Rendered markdown preview.
              </TabsContent>
              <TabsContent value="edit" className="pt-3 text-sm text-muted-foreground">
                Raw markdown editor.
              </TabsContent>
            </Tabs>
          </Row>
          <Row label="Overlays">
            <Tooltip>
              <TooltipTrigger render={<Button variant="outline" />}>
                Tooltip
              </TooltipTrigger>
              <TooltipContent>Open note · centre nebula</TooltipContent>
            </Tooltip>
            <Dialog>
              <DialogTrigger render={<Button variant="outline" />}>
                Dialog
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Compact shared memory?</DialogTitle>
                  <DialogDescription>
                    Summarises 19 of 25 lines into a durable digest. This cannot
                    be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <DialogClose render={<Button variant="outline" />}>
                    Cancel
                  </DialogClose>
                  <Button>Compact</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Sheet>
              <SheetTrigger render={<Button variant="outline" />}>
                Sheet
              </SheetTrigger>
              <SheetContent>
                <SheetHeader>
                  <SheetTitle>Backlink inspector</SheetTitle>
                  <SheetDescription>
                    Incoming links with line numbers and surrounding context.
                  </SheetDescription>
                </SheetHeader>
              </SheetContent>
            </Sheet>
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="outline" />}>
                Menu
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem>Open in editor</DropdownMenuItem>
                <DropdownMenuItem>Centre in nebula</DropdownMenuItem>
                <DropdownMenuItem>Copy path</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </Row>
          <Row label="Loading & empty">
            <div className="flex w-56 flex-col gap-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
            <Separator orientation="vertical" className="h-24" />
            <Empty className="w-72 border border-dashed border-border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <HugeiconsIcon icon={Search01Icon} />
                </EmptyMedia>
                <EmptyTitle>No messages yet</EmptyTitle>
                <EmptyDescription>
                  Ask a persona to start the conversation.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          </Row>
        </GallerySection>
      </div>
    </div>
  )
}
