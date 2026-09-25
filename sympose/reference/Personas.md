# Personas

A persona, also called an agent or a profile, is a character you chat with, each with its own voice, allowed folders and conversations. Samantha ships with Sympose and is the default. Any other persona is one you create yourself. Only Samantha has this Sympose reference, so a question about Sympose itself goes to her.

## Where does a persona live?

Each persona has its own folder, `profiles/<handle>/`, holding `persona.yaml` (its name, handle, title, allowed folders and optional model), `soul.md` (how it sounds), `sessions/` (its saved conversations) and `recaps/` (short recaps of them).

## How do I create a new persona?

Make a folder named with the handle, lowercase and one word, and put a `persona.yaml` in it, and a `soul.md` for its voice. This is the same as making a new agent or profile. Samantha cannot create personas for you yet, and the web app cannot either, so it is done by hand.

## What does a persona.yaml look like?

```
name: 'Editor'
handle: 'editor'
title: 'Proofreader'
vault_folders: ['Writing']
model: 'ollama_chat/gemma2:9b'
```

The `model` line is optional.

## What goes in a soul file?

`soul.md` holds a persona's voice and temperament: how it talks and what it is like to be with. It holds no rules and no capabilities, and is best kept around 1.5 KB. A persona without a soul file uses a plain, generic companion voice.

## Can I stop a persona from seeing some of my folders?

Yes. `vault_folders` in `persona.yaml` lists the top-level folders a persona may read, or `'*'` for all of them. It is a hard boundary: searching, note grounding, the web app and the graph all stay inside it.

## How do I switch persona or make one the default?

`/persona` switches persona. `/default` makes the current persona the one Sympose starts with, and remembers it in `settings.json` as `default_persona`.

## What is not built for personas yet?

Memory that grows as you talk, and a separate expertise file, are not built yet.
