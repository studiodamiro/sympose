# Privacy and data

## Does anything I write leave my computer?

Not by default. With the default local model, run by Ollama, everything stays on your computer: your messages, your notes and the answers. Cloud models are opt-in.

## What is sent when I use a cloud model?

Your message, the recent conversation and the note passages found for it are sent to that provider. The vault itself is never uploaded as a whole. A recap of a finished conversation, when recaps are on, also sends your messages from it.

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
