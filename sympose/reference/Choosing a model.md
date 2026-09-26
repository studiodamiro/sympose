# Choosing a model

## Which model does Sympose use out of the box?

The default is `ollama_chat/gemma2:9b`, a local model run by Ollama. Ollama has to be running and the model pulled with `ollama pull gemma2:9b`.

## How do I switch to a different model?

Type `/model` in the chat to open a picker: Gemma2:9b (local, default), Claude Sonnet 5 (cloud), GPT-4o mini (cloud), Gemini Flash (cloud), Gemini Pro (cloud), and Claude Haiku 4.5, Llama 3.3 70B, Llama 3.1 8B and DeepSeek V4 Flash through OpenRouter (cloud). The pick applies to your current conversation.

## Which model runs when there are several choices?

In order: your `/model` pick, then the `model` line in the persona's `persona.yaml`, then `chat_model` in `settings.json`, then the built-in default.

## Can I use any other model?

Yes. `chat_model` and a persona's `model` accept any model name litellm understands, such as another local Ollama model like `ollama_chat/qwen3:8b`.

## How do cloud models work?

Cloud models are opt-in and need the provider's API key in `.env`: `ANTHROPIC_API_KEY` for Claude, `OPENAI_API_KEY` for GPT, `GEMINI_API_KEY` for Gemini and `OPENROUTER_API_KEY` for the OpenRouter ones.

## What does a cloud model receive?

Your messages and the conversation are sent to that provider. Your notes, their properties and your recaps are sent only if you allow them: Sympose asks when you switch from a local model to a cloud one, and /share changes it later.

## Can I use another OpenRouter model?

Yes. Name it in `chat_model` or a persona's `model`, for example `openrouter/mistralai/mistral-large-2512`.

## Why is a thinking model so slow?

A local reasoning model such as qwen3:8b spends a long time thinking before it answers. The extra search for follow-up questions is skipped for a model that cannot do it in time.
