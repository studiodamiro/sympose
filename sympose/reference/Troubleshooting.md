# Troubleshooting

## It says it cannot connect to the model

Make sure Ollama is running (open the Ollama app, or run `ollama serve`) and that the default model is pulled with `ollama pull gemma2:9b`. If Ollama runs at another address, set `OLLAMA_API_BASE` in `.env`. For a cloud model, check that its API key is set in `.env`.

## Why is the first reply so slow?

Ollama loads the model into memory on the first message, and again after it has sat idle for a while, so the first reply takes longer than the rest. A long or resumed conversation is also slow to start, because the whole conversation is read again.

## How do I make a long conversation start faster?

A smaller `context_window` in `settings.json` shortens the wait, at the price of remembering less.

## She says she cannot find something that is in my vault

The search matches words, so try the words the note itself uses. Also check that the right vault is active and that the persona is allowed to see that folder (`vault_folders`).

## She says she cannot see my notes

No vault may be configured. Set `VAULT_PATHS` in `.env` to your vault folder.

## A reply stops mid-sentence

It reached its length limit. Raise `reply_limit` in `settings.json`.
