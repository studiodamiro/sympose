# Choosing a model

## Which model does Sympose use out of the box?

The default is `ollama_chat/gemma2:9b`, a local model run by Ollama. Ollama has to be running and the model pulled with `ollama pull gemma2:9b`.

## How do I switch to a different model?

Type `/model` in the chat to open a picker: Gemma2:9b (local, default), Claude Sonnet 5 (cloud) and GPT-4o mini (cloud). The pick applies to your current conversation.

## Which model runs when there are several choices?

In order: your `/model` pick, then the `model` line in the persona's `persona.yaml`, then `chat_model` in `settings.json`, then the built-in default.

## Can I use any other model?

Yes. `chat_model` and a persona's `model` accept any model name litellm understands, such as another local Ollama model like `ollama_chat/qwen3:8b`.

## How do cloud models work?

Cloud models are opt-in and need the provider's API key in `.env`: `ANTHROPIC_API_KEY` for Claude and `OPENAI_API_KEY` for GPT. With a cloud model, your message, the recent conversation and any matching note passages are sent to that provider.

## Why is a thinking model so slow?

A local reasoning model such as qwen3:8b spends a long time thinking before it answers. The extra search for follow-up questions is skipped for a model that cannot do it in time.
