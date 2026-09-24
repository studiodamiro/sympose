# Obsidian

## Does Sympose work with Obsidian?

Yes. Sympose is built around Obsidian vaults, and it is an independent project, not part of Obsidian. An Obsidian vault is a folder of plain markdown files, and that is all Sympose reads.

## Do I need Obsidian open or installed?

No. Sympose does not need Obsidian to be running or installed, and it does not use an Obsidian plugin. It reads the files in your vault folder directly.

## Which files does Sympose read?

It reads files ending in .md, .markdown and .txt, including their frontmatter (the block between two --- lines at the top), and takes a note's title and tags from there.

## Which folders does Sympose skip?

Sympose skips folders that hold no notes of yours: .obsidian, .git, Attachments, Drawings and .trash, plus any folder whose name starts with a dot. So it does not read your attachments folder.

## Does Sympose use my links?

Yes. Wikilinks between notes, like [[Another note]], are what the Knowledge Nebula graph in the dashboard draws.

## Does Sympose change my notes?

The chat only reads your vault. The dashboard's editor is the only part that writes, and what it saves are ordinary edits to the markdown files, the same files Obsidian shows.
