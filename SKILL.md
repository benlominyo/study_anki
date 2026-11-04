---
name: study_anki
description: "Use when creating, revising, validating, or exporting Anki flashcards or decks from notes, Markdown, PDFs, textbooks, or raw text; when the user mentions Anki, flashcards, .apkg, deck specifications, gcanki, or the Anki generation workflow."
---

# Anki deck generation

Use this skill for the full Anki deck workflow in `study_anki`. The current repo contract and the local contract files are authoritative; do not invent a parallel schema, prompt format, or export path.

## Read first

Before planning or generating cards, read the current local contract files in `study_anki`:

1. `ANKI_CARD_GENERATION_PROMPT.md`
2. `DECK_SPEC_TEMPLATE.md`
3. `anki_deck_builder.py`
4. `deck_spec_helpers.py`
5. `README.md`

Treat those files as the source of truth for card shape, wording style, highlighting, hooks, NB rules, and export behavior.

## Canonical deck shape

The deck specification is JSON with deck-level fields and a `cards` array. Each card must stay within the current contract:

- `front`: one focused question that can be answered unambiguously on its own.
- `back`: exactly two HTML `<p>` paragraphs in formal textbook style.
- `recall_hook`: separate metadata with one short sentence and one allowed color.
- `nb`: separate metadata with `mode: "actionable"` and a concrete, ecosystem-specific computational step.
- `tags`: specific, useful tags that preserve the topic.

Do not place hook or NB content inline in the back. Keep the answer field clean and let metadata carry the extra framing.

## Wording and content rules

- Write every card in precise, polished textbook prose.
- Keep each card atomic: one fact, relationship, definition, or procedure.
- Make the front context-complete without leaking the answer.
- Preserve technical notation, units, thresholds, named methods, and causal direction exactly.
- Use compact Unicode math notation where needed; do not use raw LaTeX.
- Write exactly two focused `<p>` paragraphs in the authored back. Paragraph 1 states the core definition, model, mechanism, or procedure; paragraph 2 adds a distinct consequence, contrast, limitation, or application. No exceptions.
- Distribute tier-2 highlights across both authored paragraphs: mark at least one distinct, source-supported high-yield term in each paragraph. Prefer two or three useful terms total per card when available; do not highlight filler or repeat a term just to meet a count. Author the distribution in the spec because builder fallback styling does not guarantee it.

## Recall hook rules

- Every card must have exactly one recall hook.
- The hook stays in `recall_hook`, not in the back HTML.
- It must be a single sentence that reinforces the one concept on the card without adding new information.
- Allowed colors are blue, red, purple, and navy.

## NB rules

- Every card must have exactly one NB.
- `nb.mode` must be `"actionable"`.
- The NB must name a concrete tool, function, method, or short workflow that a learner could actually run.
- Make the NB ecosystem-specific and concept-specific.
- Vary the NB across the deck; do not reuse the same idea repeatedly.
- Broaden the ecosystem choices when drafting NB notes. Use the ecosystem that best fits the concept, including Python, R/RStudio, SQL/PostgreSQL, NoSQL, Excel/M365, Google Sheets, MATLAB/Octave, Julia, SAS, SPSS, Stata, Tableau, Power BI, Spark/PySpark, dbt, Git, GitHub Actions, Linux/Bash, Docker, Jupyter, Quarto, REST/JSON, C, C++, Java, JavaScript, NONMEM, Monolix, Phoenix WinNonlin, REDCap, QGIS, ImageJ, and similar concrete workflows.
- Consult the compact concept-family/tool/action registry and fixed structural templates in `study_anki/deck_spec_helpers.py`; adapt the chosen operation to the card, avoid repeating the same operation within a deck, and keep final content in card metadata.
- If a card does not seem to support a good NB, rewrite the card or choose a better computational angle rather than falling back to a non-actionable note.

## Generation workflow

1. Read the source material and identify supported concepts.
2. Set the card budget from distinct source-supported concepts. Do not pad with duplicates, thin paraphrases, or unsupported claims.
3. Interpret requested counts literally: `exactly N` means N supported cards; `at least N` is a minimum only when the source supports it. If the source cannot support a hard requested count, stop and report the supported count instead of inventing content.
4. Before drafting each card, select one distinct actionable NB operation. If no direct operation fits, narrow the concept and use a truthful adjacent inspect/query/visualize/simulate/validate/transform workflow; never omit NB metadata.
5. Draft the complete deck spec in one pass, using only the canonical JSON shape.
6. Return only the JSON object; include no preface, progress text, explanation, or trailing commentary.
7. Make sure every card has exactly two authored `<p>` paragraphs, one recall hook, and one actionable NB. Hook and NB metadata are rendered outside the paragraphs.
8. Ensure key terms are marked and tier-2 highlights are distributed across both paragraphs, with at least one distinct, source-supported term per paragraph and varied soft colors across the deck.
9. Use the canonical builder in `study_anki` to validate and export the deck.
10. If the builder reports a validation problem, correct the failing spec content and retry only the targeted build; do not ask the builder to rewrite content.

## Validation and export

The canonical builder is the handoff point. Do not bypass it, and do not present an unvalidated deck as complete. If the builder rejects the spec, repair the spec rather than adding ad hoc workarounds.

## Recovery

When resuming work, read the current source files and any persisted run artifacts before continuing. Do not rely on memory of an older workflow if it conflicts with the local contract.
