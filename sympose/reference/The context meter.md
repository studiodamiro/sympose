# The context meter

## What does the percentage under the chat box mean?

Under the chat box a dim line like `context ██████░░░░ 62%` shows how full the conversation is. A model can only read so much at once, and the percentage is how much of that space your conversation uses, after keeping room for the reply. At 100% the next message starts leaving older turns out.

## When does the meter change?

Once per reply, not while you type. It leans a little high on purpose, turns warning colour from 70% and error colour from 90%, is empty before the first reply, and is cleared when you switch model or persona until the next reply.

## What does older turns out of context mean?

When the conversation no longer fits, the oldest exchanges are left out of what the model reads and the reply header says so, for example "3 older turns out of context". The model no longer sees them, but they stay saved in your conversation file.

## What else gets left out?

If the notes she found do not fit either, the weakest ones are left out next. Her voice and rules are never left out.

## How do I make more room?

A larger window remembers more but makes the first reply of a long conversation slower. `context_window` in `settings.json` sets it, and starting a fresh conversation also clears the space.

## What does reply cut at the length limit mean?

The reply reached its length limit. Raise `reply_limit` in `settings.json` to allow longer replies.

## How do I hide the meter?

Set `show_context_meter` to `false` in `settings.json`.
