# How Samantha uses your notes

## How does Samantha find my notes?

Every message you send is looked up in your vault first. The best matching passages, a few sentences each and up to five, go to the model together with your message, and the answer is meant to come from them. This is called grounding. By default the lookup goes by meaning, not only by words.

## What does searching by meaning mean?

Samantha compares what your message is about with what each passage is about, not just the words. A small model turns both into lists of numbers, and passages whose numbers are close to your message's are used. So "what did we settle on for backups?" can find a note that only says rsync.

## Do I have to set anything up for searching by meaning?

It is on by default, as `auto`. It needs one small model in Ollama, pulled once with `ollama pull nomic-embed-text`. Without it, or when Ollama is not running, Samantha quietly searches by keyword instead. Nothing breaks, the search is just less smart.

## Is my vault sent anywhere for searching by meaning?

No. The small model runs in your Ollama on your computer, and the numbers for each passage are kept in a cache file, `embedding_cache.sqlite`, beside `settings.json`. Only if you set an `embedding_model` from a cloud provider, and allow notes for cloud models with /share, would passages leave your computer; without that yes she searches by keywords.

## What does indexing 40% mean?

The first time, Samantha reads all your notes into that cache in the background, a minute or two for a big vault, and shows how far along she is at the right end of the line under the chat box. Until it is done she searches by keyword, so you can chat at once. Later launches only read notes that changed.

## Why does she miss a note, or bring notes that have nothing to do with my question?

For fewer unrelated notes, raise `embedding_min_similarity` in `settings.json` (0.72 by default); if she misses notes, lower it. `embedding_margin` (0.02) drops notes that are not nearly as close as the best one. A note you name only by a very short title may need a few more words about it.

## How do I go back to searching by words only?

Set `grounding_search` to `"keywords"` in `settings.json`. She then never uses the small model and does not build the cache.

## What does the reply header show?

Above each reply Samantha shows a line like `@samantha · Gemma2:9b · TTFT 8.3s · from Notes/Example.md +1`. It gives the model, then TTFT, which is the time until the first word appeared.

## What does the from part in the reply header mean?

`from` names the note that grounded the reply, the note the answer was taken from, and `+1` says one more note was also used. If nothing follows the TTFT, no note matched.

## What does searched mean in the header?

`searched "..."` appears after a follow-up question and shows the search Samantha wrote for it.

## How does she handle follow-up questions?

A message such as "why did we pick it?" has no words to search for. When the first search finds nothing and there is earlier conversation, one small extra model call rewrites the question into a standalone search using the last two exchanges. The rewrite only feeds the search and is never shown to the model as something you said.

## What if nothing matches?

Samantha says she could not find it in your vault instead of inventing an answer. If the note is there, ask again with a few more words about it, or with the words the note itself uses.

## Which notes may she read?

Only the folders the persona is allowed to see (`vault_folders`), in the active vault.

## How do I hide the notes she used?

Type `/grounding` to hide or show the note line in the reply header. The `show_grounding` setting does the same.

## How do I turn off the follow-up search?

Set `grounding_followups` to `"off"` in `settings.json` to stop the extra search for follow-up questions.
