# Privacy and data

## Does anything I write leave my computer?

Not by default. With the default local model, run by Ollama, everything stays on your computer: your messages, your notes and the answers. Cloud models are opt-in.

## What is sent when I use a cloud model?

Your messages and the conversation so far are always sent to that provider. What comes from your vault is sent only if you allow it, one kind at a time: your notes, their properties and your recaps. None is allowed by default. The vault itself is never uploaded as a whole.

## How do I let a cloud model use my notes?

When you switch from a local model to a cloud one with /model, Sympose asks about each kind. Type /share to see or change what is allowed; it is kept in `cloud_share` in `settings.json`. A cloud reply's header shows `cloud:` for what was sent and `withheld:` for what was held back.

## Is a recap sent to a cloud model?

A recap written by a cloud model sends your messages from that conversation, so it is written only when recaps are allowed for cloud models.

## Where are my conversations stored?

Conversations are stored on your computer, saved as they happen, one file per conversation, in the persona's `sessions` folder: `profiles/<handle>/sessions/`. The files are plain text (JSON lines), and deleting one deletes that conversation.

## Where are the recaps of my conversations kept?

In the persona's `recaps` folder, `profiles/<handle>/recaps/`, beside `sessions`: one small text file per conversation, written on your computer from your own messages. Open one to read or correct it. To stop one coming back, empty it: a deleted recap is written again. `session_recaps` in `settings.json` turns recaps off.

## Does the chat change my notes?

No. Your notes stay where they are, in your vault, and the chat never changes them.

## Where are my settings?

In `settings.json`. Nothing is sent anywhere else.

## Are my conversations committed to git?

No. Saved conversations and their recaps are ignored by git for every persona, so they are never committed to the project's repository.
