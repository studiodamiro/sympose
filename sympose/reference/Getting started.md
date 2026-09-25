# Getting started

These are the steps as of version 0.1.0.

## What do I need to run Sympose?

You need Python 3.11 or newer, an Obsidian vault (any folder of markdown notes), and Ollama running on your computer with the default model pulled: `ollama pull gemma2:9b`.

## How do I set Sympose up?

Copy the file `.env.example` to `.env`, set `VAULT_PATHS` in it to the folder of your vault, then run `pip install -e ".[dev]"` from the project folder.

## How do I start chatting in the terminal?

Run `sympose cli`. You talk to Samantha, the default persona. Type / to see the commands.

## How do I start the web app?

Run `sympose web`, then open http://127.0.0.1:8000 in your browser. It serves the web app and its API together, on your computer only. `--port` or `PORT` in `.env` changes the port, and Ctrl-C stops it.

## How do I work on the web app itself?

Run `python -m sympose.main` for the API, and from the `ui` folder run `npm install` once and `npm run dev`, which serves the app with live reload on localhost:5173.

## What if something does not work?

See Troubleshooting.
