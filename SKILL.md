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
- Every card must have exactly two back paragraphs, each with 2–3 complete sentences, and 400–550 visible characters total (200–275 visible characters per paragraph; raw HTML typically 500–830). Paragraph 1 explains the core what/how; paragraph 2 adds a real consequence, assumption, caveat, interpretation, or mechanism, never a one-line restatement.
- Tier-2 density is mandatory: 2–4 spans in paragraph 1 and 2–3 in paragraph 2 (4–7 total); never leave either paragraph unhighlighted. Span text is 1–4-word noun phrases, never clauses. Never nest Tier-2 spans. Never repeat a highlighted phrase within a card; Tier-2 markup is not in the Recall hook or NB metadata. When spans are removed, the prose must remain grammatical.
- Use only the eight classes with base `tier2`: `tier2-blue`, `tier2-purple`, `tier2-orange`, `tier2-green`, `tier2-teal`, `tier2-red`, `tier2-pink`, and `tier2-lightblue`. Every card uses at least two core colors (blue, purple, orange, green); use at most one span per secondary color (teal, red, pink, lightblue). A color marks only its fixed role:

| Color | Fixed role |
| --- | --- |
| blue | Anchor concept |
| purple | Contrast or second concept |
| orange | Condition, constraint, or design point |
| green | Added factor or consequence |
| teal | Time-course or procedural detail |
| red | Limiting or cautionary mechanism |
| pink | Transition or shape marker |
| lightblue | Notation, symbol, or named statistic |

- `tier2-lightblue` uses foreground `#7bbddc`. The builder preserves authored spans and validates the contract; it does not invent or recolor them. Before returning cards, verify the length, per-paragraph density, sentence, phrase, palette-role, nesting, and placement rules for every card.

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
8. Self-check every card against the mandatory Tier-2 contract and fixed color-role table above: length and sentence counts, per-paragraph span ranges, phrase length and uniqueness, color-role limits, nesting, placement, and grammatical prose after markup removal. The builder preserves authored spans but does not invent or recolor them.
9. Use the canonical builder in `study_anki` to validate and export the deck.
10. If the builder reports a validation problem, correct the failing spec content and retry only the targeted build; do not ask the builder to rewrite content.

## Validation and export

The canonical builder is the handoff point. Do not bypass it, and do not present an unvalidated deck as complete. If the builder rejects the spec, repair the spec rather than adding ad hoc workarounds.

## Recovery

When resuming work, read the current source files and any persisted run artifacts before continuing. Do not rely on memory of an older workflow if it conflicts with the local contract.
