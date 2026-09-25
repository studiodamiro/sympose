# What is Sympose

Sympose is a personal AI companion for an Obsidian vault. You chat with a persona, Samantha by default, and she answers from the notes in your vault instead of guessing.

## Who made Sympose?

Sympose was made by damiro, who is its author.

## What is Sympose for?

Sympose is for asking about what you already wrote: decisions, plans, people, recipes, meeting notes. When the answer is not in your vault, Samantha says she could not find it instead of making something up.

## How does Sympose keep the cost down?

Sympose finds the relevant notes itself with plain keyword search, then makes one model call per message to answer from them, so there is no chain of expensive model calls behind each question. Only a follow-up question with no searchable words of its own costs one extra small model call.

## Does Sympose cost money to run?

Not by default. It runs on a local model, so a message costs nothing beyond your own computer. A cloud model is an opt-in choice and is billed by its provider.

## What is Sympose made of?

Sympose has a chat in the terminal where you talk to a persona, a web app in the browser (a vault tree, a markdown editor, search and a graph of your notes), and personas: Samantha ships with Sympose and you can create your own.
