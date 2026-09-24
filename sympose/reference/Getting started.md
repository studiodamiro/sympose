# Getting started

These are the steps as of version 0.1.0.

## What do I need to run Sympose?

You need Python 3.11 or newer, an Obsidian vault (any folder of markdown notes), and Ollama running on your computer with the default model pulled: `ollama pull gemma2:9b`.

## How do I set Sympose up?

Copy the file `.env.example` to `.env`, set `VAULT_PATHS` in it to the folder of your vault, then run `pip install -e ".[dev]"` from the project folder.

## How do I start chatting in the terminal?

Run `python -m sympose.cli`. You talk to Samantha, the default persona. Type / to see the commands.

## How do I start the dashboard?

Start the backend with `python -m sympose.main`, which serves on 127.0.0.1:8000. Then, from the `ui` folder, run `npm install` once and `npm run dev`, which serves the dashboard on localhost:5173.

## What if something does not work?

See Troubleshooting.
