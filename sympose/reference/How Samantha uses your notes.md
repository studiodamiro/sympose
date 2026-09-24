# How Samantha uses your notes

## How does Samantha find my notes?

Every message you send is searched for in your vault first. The best matching passages, a few sentences each and up to five, go to the model together with your message, and the answer is meant to come from them. This is called grounding.

## What does the reply header show?

Above each reply Samantha shows a line like `@samantha · Gemma2:9b · TTFT 8.3s · from Notes/Example.md +1`. It gives the model, then TTFT, which is the time until the first word appeared.

## What does the from part in the reply header mean?

`from` names the note that grounded the reply, the note the answer was taken from, and `+1` says one more note was also used. If nothing follows the TTFT, no note matched.

## What does searched mean in the header?

`searched "..."` appears after a follow-up question and shows the search Samantha wrote for it.

## How does she handle follow-up questions?

A message such as "why did we pick it?" has no words to search for. When the first search finds nothing and there is earlier conversation, one small extra model call rewrites the question into a standalone search using the last two exchanges. The rewrite only feeds the search and is never shown to the model as something you said.

## What if nothing matches?

Samantha says she could not find it in your vault instead of inventing an answer. The search is by words, so a question that uses different words from the note may miss it. Try the note's own words.

## Which notes may she read?

Only the folders the persona is allowed to see (`vault_folders`), in the active vault.

## How do I hide the notes she used?

Type `/grounding` to hide or show the note line in the reply header. The `show_grounding` setting does the same.

## How do I turn off the follow-up search?

Set `grounding_followups` to `"off"` in `settings.json` to stop the extra search for follow-up questions.
