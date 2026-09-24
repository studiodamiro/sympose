# Privacy and data

## Does anything I write leave my computer?

Not by default. With the default local model, run by Ollama, everything stays on your computer: your messages, your notes and the answers. Cloud models are opt-in.

## What is sent when I use a cloud model?

Your message, the recent conversation and the note passages found for it are sent to that provider. The vault itself is never uploaded as a whole; only the few passages found for a message are sent.

## Where are my conversations stored?

Conversations are stored on your computer, saved as they happen, one file per conversation, in the persona's `sessions` folder: `profiles/<handle>/sessions/`. The files are plain text (JSON lines), and deleting one deletes that conversation.

## Does the chat change my notes?

No. Your notes stay where they are, in your vault, and the chat never changes them.

## Where are my settings?

In `settings.json`. Nothing is sent anywhere else.

## Are my conversations committed to git?

No. Saved conversations, and any persona memory once it exists, are ignored by git for every persona, so they are never committed to the project's repository.
