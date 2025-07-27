# Hippo: AI-Generated Insights Memory System

*An experiment in collaborative memory through reinforcement learning*

## Overview

Hippo is a memory system designed to let insights emerge organically through usage patterns. It supplies the LLM with tools to record insights and then later to indicate which ones are useful via up/down-voting (similar to reddit or stack overflow) and to make edits.

## Design principles

* **Embrace the mess.** What makes LLMs amazing is that, like humans, they *don't* require formal structure or precision to extract meaning. Hippo avoids structure and instead aims to surface text to the LLM, letting it draw the necessary connections and interpretations.
* **Reinforce what's useful, let the rest fade.** It's very hard to know what you're going to need to remember in the future. Hippo encourages the LLM to generate lots of memories but then to "curate" the ones that turn out to be useful.
* **Mimic human systems.** Hippo is loosely inspired by human memory systems. We match not only on memory content but also on situational context for better precision. We try to leverage bits of research, but we also know that LLMs are not humans so we are willing to stray in the details.
* **Integrate with collaborative prompting patterns.** Hippo is designed to work best with the [collaborative prompting](https://socratic-shell.github.io/socratic-shell/collaborative-prompting.html) style. Memories are fetched during the [ideation and exploration](https://socratic-shell.github.io/socratic-shell/prompts/user/index.html#collaborative-exploration-patterns) phase and then reinforced and updated during ["make it so"](https://socratic-shell.github.io/socratic-shell/prompts/user/index.html#make-it-so---transitioning-to-action) and [checkpoint](https://socratic-shell.github.io/socratic-shell/prompts/user/index.html#checkpointing-your-work) moments.

## Status

Prototype implementation.