export type ActionKind = "WRITE_NOTE" | "APPEND_NOTE" | "SEARCH"

export interface ChatAction {
  kind: ActionKind
  detail?: string
}

export interface ChatTurn {
  id: string
  role: "user" | "persona"
  /** Persona handle — `role: "persona"` only. */
  handle?: string
  body: string
  timestamp?: string
  /** TTFT/latency readout — `role: "persona"` only. */
  latency?: string
  streaming?: boolean
  actions?: ChatAction[]
}

export const MOCK_TURNS: ChatTurn[] = [
  {
    id: "1",
    role: "user",
    body: "What did I write about the Q3 roadmap last week?",
    timestamp: "10:02 AM",
  },
  {
    id: "2",
    role: "persona",
    handle: "samantha",
    body: "Found it — you sketched three milestones in Planning/Q3-roadmap.md, with the multi-vault work called out as the riskiest one. Want me to pull up the actual note?",
    timestamp: "10:02 AM",
    latency: "0.61s",
    actions: [{ kind: "SEARCH", detail: "Planning/Q3-roadmap.md" }],
  },
  {
    id: "3",
    role: "user",
    body: "Not yet — just jot a follow-up under it that I still need to scope the CLI work.",
    timestamp: "10:04 AM",
  },
  {
    id: "4",
    role: "persona",
    handle: "samantha",
    body: "Added a follow-up line under the Q3 roadmap note.",
    timestamp: "10:04 AM",
    latency: "0.48s",
    actions: [
      { kind: "APPEND_NOTE", detail: "Planning/Q3-roadmap.md" },
    ],
  },
  {
    id: "5",
    role: "persona",
    handle: "samantha",
    body: "Anything else you'd like on your plate before I let you get back to it",
    timestamp: "10:04 AM",
    streaming: true,
  },
]
