# study_anki

A single, reusable workflow for turning source material into validated Anki
decks. [AI Agent] may start with notes, Markdown, PDFs, textbooks, or raw text,
but the canonical builder consumes one JSON deck specification and produces
one Anki package.

## Single generation entry point

All deck generation uses the CLI in
[`anki_deck_builder.py`](anki_deck_builder.py). There are no deck-specific
builder scripts, `coursetext_anki` pipeline, or alternate source-family
pipelines. Source material is transformed into the JSON specification before
the shared builder is invoked.

Install the runtime dependency:

```bash
python -m pip install -r requirements.txt
```

Build one validated deck from a JSON specification:

```bash
python anki_deck_builder.py --spec path/to/deck_spec.json
```

Check whether the cached `.apkg` is current without rebuilding it:

```bash
python anki_deck_builder.py --spec path/to/deck_spec.json --check
```

Force regeneration when the cache is current:

```bash
python anki_deck_builder.py --spec path/to/deck_spec.json --force
```

The specification may override the output location with `output_file`, or the
CLI may override it for a one-off build:

```bash
python anki_deck_builder.py \
  --spec path/to/deck_spec.json \
  --output build/deck.apkg
```

The builder resolves relative image paths from the specification directory and
packages referenced local images into the `.apkg`. Text-only cards require no
media directory. The output is a standard Anki package; generated `.apkg`
files and build-cache files are not source files and should remain untracked.

## Core contract

The builder performs a mandatory final normalization pass before export and
then validates the normalized result. It fails loudly with a
`CardValidationError` or specification error; it never exports a
success-shaped package containing a malformed card. Each card must have:

- a non-empty, context-complete front;
- exactly two meaningful explanatory `<p>` paragraphs in the authored back;
- exactly one Recall hook using blue, red, purple, or navy;
- exactly one non-empty, actionable NB footer inferred from the card's concept;
- preserved tags, valid HTML, images, equations, and Tier-2 styling.

Tier-2 authoring is mandatory for every card. Write exactly two back paragraphs, each with 2–3 complete sentences. The visible prose must total 400–550 characters per card (200–275 visible characters per paragraph; raw HTML is typically 500–830 characters). Paragraph 1 explains the core what/how; paragraph 2 adds a real consequence, assumption, caveat, interpretation, or mechanism, never a one-line restatement.

Use 2–4 spans in paragraph 1 and 2–3 in paragraph 2 (4–7 total); never leave either paragraph unhighlighted. Span 1–4-word noun phrases only, never clauses. Do not nest spans, repeat a highlighted phrase within a card, or put Tier-2 markup in Recall-hook or NB metadata. Removing spans must leave grammatical, formal prose.

Use only these eight classes, always with the base `tier2` class:
`tier2-blue`, `tier2-purple`, `tier2-orange`, `tier2-green`, `tier2-teal`, `tier2-red`, `tier2-pink`, and `tier2-lightblue`. The core colors—blue, purple, orange, and green—are used first and in most cards; every card uses at least two core colors. At most one span per secondary color (teal, red, pink, lightblue) is allowed per card. A color marks only its assigned role:

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

The `tier2-lightblue` foreground is `#7bbddc`. Author spans as `<span class="tier2 tier2-{color}">…</span>`. The builder preserves authored spans and validates the contract; it does not invent or recolor highlights. Before returning the cards, perform this per-card editorial check: verify two paragraphs and 2–3 sentences each; 400–550 visible characters; 2–4 spans in paragraph 1 and 2–3 in paragraph 2; 1–4-word noun phrases; at least two core colors; no nested spans, duplicate phrases, unsupported classes, or spans outside the answer paragraphs; and grammatical prose after removing markup.

Preferred PHM4510 example (adapted from the real concentration–response design card; copy the markup pattern and density, not the content):

```html
<p>When potency or sigmoidicity varies between individuals, the <span class="tier2 tier2-blue">population-average concentration–response curve</span> may not resemble any <span class="tier2 tier2-purple">individual curve</span>. A design optimized around that pooled mean can therefore miss the concentration regions that characterize individual responses.</p>
<p>Sampling across the plausible parameter range makes the design more robust to parameter uncertainty and <span class="tier2 tier2-green">between-subject variability</span>. This broader coverage preserves interpretability for individuals whose response differs from the <span class="tier2 tier2-orange">nominal curve</span>.</p>
```

The builder rejects backs with fewer or more than two meaningful `<p>`
paragraphs. It does not rewrite card meaning, remove valid HTML, or remove
referenced media.

## Card metadata

```json
{
  "front": "What condition defines pharmacokinetic steady state?",
  "back": "<p>...</p><p>...</p>",
  "recall_hook": {
    "color": "navy",
    "text": "Steady state represents balance between input and elimination."
  },
  "nb": {
    "mode": "actionable",
    "text": "In R, mrgsolve::mrgsim() can simulate repeated dosing."
  },
  "tags": ["pharmacokinetics"]
}
```

Every card must use `nb.mode="actionable"`. The note may name a direct
implementation or an honest adjacent workflow such as a query, visualization,
simulation, diagnostic, or data transformation. Do not reuse the same exact NB
idea across cards.

Run the focused tests with:

```bash
python -m unittest discover -s . -p 'test_*.py' -v
```

## Supported specification shape

The required top-level fields are `deck_name` and `cards`. Optional fields
include `model_name`, `deck_id`, `model_id`, `output_file`, and `css`.
Each card uses `front`, `back`, optional `tags`, optional `images`, and
metadata objects named `recall_hook` and `nb` when the corresponding block is
not already present in the back. See
[`DECK_SPEC_TEMPLATE.md`](DECK_SPEC_TEMPLATE.md) for the authoring contract
and [`ANKI_CARD_GENERATION_PROMPT.md`](ANKI_CARD_GENERATION_PROMPT.md) for
the OpenClaw generation instructions.

## License

Copyright (c) 2026 benlominyo. Released under the [MIT License](LICENSE).
If you use or adapt this work, please keep the copyright notice and credit the original author.
