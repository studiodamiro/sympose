import { describe, expect, it } from "vitest"

import { extractWikilinks } from "./extract-wikilinks"

describe("extractWikilinks", () => {
  it("extracts a plain [[target]] link", () => {
    expect(extractWikilinks("see [[Some Note]] for details")).toEqual(["Some Note"])
  })

  it("strips the |label from a piped link, keeping only the target", () => {
    expect(extractWikilinks("see [[Some Note|a note]]")).toEqual(["Some Note"])
  })

  it("dedupes repeated targets in first-seen order", () => {
    expect(extractWikilinks("[[B]] then [[A]] then [[B]] again then [[A|alias]]")).toEqual([
      "B",
      "A",
    ])
  })

  it("returns an empty array when there are no links", () => {
    expect(extractWikilinks("just plain text, no links here")).toEqual([])
  })
})
