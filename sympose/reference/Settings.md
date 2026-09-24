# Settings

Settings are stored in `settings.json`, in the folder where Sympose runs. `SYMPOSE_SETTINGS_PATH` in `.env` moves the file. There is no settings screen yet, so you edit the file by hand. Restart the chat after editing to be sure a change applies.

## Where are my settings stored?

In `settings.json`, in the folder where you run Sympose, or wherever `SYMPOSE_SETTINGS_PATH` points.

## active_vault

The `active_vault` setting is the vault in use. It is set by the dashboard's workspace switcher.

## added_vaults

The `added_vaults` setting holds the vaults you added from the dashboard's workspace switcher.

## chat_model

The `chat_model` setting is the model used when no persona or `/model` pick decides otherwise. The default is `ollama_chat/gemma2:9b`.

## default_persona

The `default_persona` setting is the persona Sympose starts with. It is set by `/default`.

## context_window

The `context_window` setting is the size in tokens of the conversation a local model is given. By default it follows the model's own window, up to 32768. A number you set is used as your own ceiling, and a value below 2048 is raised to 2048.

## reply_limit

The `reply_limit` setting is the tokens kept back for the reply. By default a quarter of the window, up to 4096.

## show_grounding

Setting `show_grounding` to `false` hides the notes in the reply header.

## show_trim_notice

Setting `show_trim_notice` to `false` hides the notice that older turns were left out.

## show_context_meter

Setting `show_context_meter` to `false` hides the meter under the chat box.

## session_recaps

Setting `session_recaps` to `false` stops Samantha writing and reading recaps of your earlier conversations. Each recap is written by the model from your own messages, so with a cloud model those messages are sent to the provider.

## grounding_followups

Setting `grounding_followups` to `"off"` stops the extra search for follow-up questions.

## How do the true or false settings work?

Only an explicit `false` turns a setting off. Anything else leaves the default.

## Which settings go in .env?

`VAULT_PATHS` (your vaults, comma separated), `SYMPOSE_PROFILES_DIR` (where persona folders live, default `./profiles`), `SYMPOSE_SETTINGS_PATH`, `OLLAMA_API_BASE` (an Ollama server that is not at the default address) and `PORT` (the dashboard backend's port, default 8000).
