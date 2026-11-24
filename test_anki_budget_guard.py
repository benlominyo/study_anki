import json
import re
import tempfile
import unittest
from pathlib import Path

from anki_deck_builder import DEFAULT_CSS, CardValidationError, build_deck, inspect_spec, normalize_card, should_skip_creation
from deck_spec_helpers import PALETTE, auto_highlight_key_terms, tier2


class AuthoringPaletteContractTests(unittest.TestCase):
    DOC_NAMES = (
        "ANKI_CARD_GENERATION_PROMPT.md",
        "DECK_SPEC_TEMPLATE.md",
        "README.md",
        "SKILL.md",
    )
    PALETTE_NAMES = ("blue", "red", "green", "lightblue", "pink", "orange", "purple", "teal")

    def test_authoring_docs_require_both_paragraphs_and_canonical_palette(self):
        root = Path(__file__).parent
        for name in self.DOC_NAMES:
            with self.subTest(document=name):
                content = " ".join((root / name).read_text(encoding="utf-8").casefold().split())
                self.assertIn("lightblue", content)
                self.assertIn("#7bbddc", content)
                self.assertIn("at least one purposeful tier-2 span is required in each explanatory paragraph of every card", content)
                self.assertIn("2–5", content)
                for color in self.PALETTE_NAMES:
                    self.assertIn(color, content)
                self.assertNotIn("gold", content)
                self.assertNotRegex(content, r"bold[- ]red|answer[- ]target|answer target")
                self.assertNotIn("no per-card quota", content)

    def test_authoring_prompt_requires_authored_tier2_and_explains_density(self):
        prompt = " ".join(
            (Path(__file__).parent / "ANKI_CARD_GENERATION_PROMPT.md")
            .read_text(encoding="utf-8")
            .casefold()
            .split()
        )
        self.assertIn(
            "at least one purposeful tier-2 span is required in each explanatory paragraph of every card",
            prompt,
        )
        self.assertIn("typically 2–5 purposeful spans total", prompt)
        self.assertIn("do not leave either paragraph unhighlighted", prompt)
        self.assertIn("never nest tier-2 spans", prompt)
        self.assertIn("not in the recall hook or nb metadata", prompt)
        self.assertIn("when spans are removed, the prose must remain grammatical", prompt)

    def test_authoring_prompt_demonstrates_valid_tier2_markup(self):
        prompt = (Path(__file__).parent / "ANKI_CARD_GENERATION_PROMPT.md").read_text(encoding="utf-8")
        match = re.search(r"Preferred PHM4510 example.*?```html\n(.*?)```", prompt, re.DOTALL)
        self.assertIsNotNone(match, "a preferred PHM4510-derived HTML example is required")
        example = match.group(1)
        self.assertIn("P = TVP + ETA", example)
        paragraphs = re.findall(r"<p>(.*?)</p>", example, re.DOTALL)
        self.assertEqual(len(paragraphs), 2)
        all_colors = []
        for paragraph in paragraphs:
            spans = re.findall(
                r'<span class="tier2 tier2-([a-z]+)">(.*?)</span>',
                paragraph,
                re.DOTALL,
            )
            self.assertTrue(spans, "each explanatory paragraph must demonstrate at least one span")
            for color, body in spans:
                self.assertIn(color, self.PALETTE_NAMES)
                self.assertNotIn("<span", body)
                all_colors.append(color)
        self.assertGreaterEqual(len(all_colors), 2)
        self.assertLessEqual(len(all_colors), 5)
        self.assertGreaterEqual(len(set(all_colors)), 2)


class PaletteRenderingTests(unittest.TestCase):
    @staticmethod
    def card(back):
        return {
            "front": "What does the highlighted term mean?",
            "back": back,
            "recall_hook": {"color": "navy", "text": "The hook restates the concept."},
            "nb": {"mode": "actionable", "text": "Use pandas.DataFrame.describe() to inspect the values."},
        }

    def test_lightblue_palette_value_and_css_are_consistent(self):
        self.assertEqual(PALETTE["lightblue"], "#7bbddc")
        self.assertNotIn("gold", PALETTE)
        self.assertIn(".tier2-lightblue { background: #eaf2fb; color: #7bbddc; }", DEFAULT_CSS)
        self.assertNotIn(".tier2-gold", DEFAULT_CSS)

    def test_tier2_helper_emits_lightblue_markup(self):
        self.assertEqual(
            tier2("retrieval term", "lightblue"),
            '<span class="tier2 tier2-lightblue">retrieval term</span>',
        )

    def test_tier2_helper_rejects_unsupported_color(self):
        with self.assertRaisesRegex(ValueError, "unsupported Tier-2 color"):
            tier2("retrieval term", "violet")

    def test_normalization_migrates_legacy_class_and_preserves_authored_spans(self):
        normalized = normalize_card(
            self.card(
                '<p>First <span class="key tier2 tier2-gold">light-blue phrase</span>.</p>'
                '<p>Second <span class="tier2 tier2-green">related term</span>.</p>'
            ),
            deck_name="Palette Deck",
            card_index=3,
        )
        self.assertIn('<span class="key tier2 tier2-lightblue">light-blue phrase</span>', normalized["back"])
        self.assertIn('<span class="tier2 tier2-green">related term</span>', normalized["back"])

    def test_normalization_rejects_unsupported_tier2_class_with_card_context(self):
        with self.assertRaisesRegex(CardValidationError, r"Palette Deck.*card 4.*unsupported Tier-2 color 'violet'"):
            normalize_card(
                self.card(
                    '<p>First <span class="tier2 tier2-violet">term</span>.</p>'
                    "<p>Second paragraph.</p>"
                ),
                deck_name="Palette Deck",
                card_index=4,
            )

    def test_normalization_parses_actual_class_attribute_across_attribute_order_and_quoted_gt(self):
        for opening_tag in (
            '<span data-class="annotation" class="tier2 tier2-violet">',
            '<span title="x > y" class="tier2 tier2-violet">',
        ):
            with self.subTest(opening_tag=opening_tag):
                with self.assertRaisesRegex(CardValidationError, "unsupported Tier-2 color 'violet'"):
                    normalize_card(
                        self.card("<p>First " + opening_tag + "term</span>.</p><p>Second paragraph.</p>"),
                        deck_name="Palette Deck",
                        card_index=6,
                    )

    def test_data_class_does_not_trigger_tier2_normalization(self):
        normalized = normalize_card(
            self.card(
                '<p>First <span data-class="tier2 tier2-violet">annotation</span>.</p>'
                "<p>Second paragraph.</p>"
            ),
            deck_name="Palette Deck",
            card_index=7,
        )
        self.assertIn('data-class="tier2 tier2-violet"', normalized["back"])

    def test_key_term_highlighter_preserves_authored_tier2_color(self):
        back = (
            '<p>First <span class="tier2 tier2-green">time series</span>.</p>'
            "<p>Second paragraph.</p>"
        )
        self.assertEqual(
            auto_highlight_key_terms("Explain time series", back, title="Time Series"),
            back,
        )

    def test_normalization_rejects_incomplete_tier2_class(self):
        with self.assertRaisesRegex(CardValidationError, "Tier-2 span must include exactly one supported color class"):
            normalize_card(
                self.card('<p>First <span class="tier2">term</span>.</p><p>Second paragraph.</p>'),
                deck_name="Palette Deck",
                card_index=5,
            )


class PaletteInspectionTests(unittest.TestCase):
    @staticmethod
    def inspect(back, deck_name="Palette Inspection"):
        spec = {
            "deck_name": deck_name,
            "cards": [
                {
                    "front": f"What is the main concept in {deck_name}?",
                    "back": back,
                    "recall_hook": {"color": "navy", "text": "The hook restates the concept."},
                    "nb": {"mode": "actionable", "text": "Use pandas.DataFrame.describe() to inspect the values."},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            return inspect_spec(spec, Path(tmpdir))

    def test_inspection_counts_only_authored_spans_in_the_two_paragraphs(self):
        summary = self.inspect(
            '<p>First <span class="tier2 tier2-blue">blue one</span> and '
            '<span class="tier2 tier2-red">red one</span>.</p>'
            '<p>Second <span class="tier2 tier2-lightblue">light blue</span>.</p>'
            '<div class="callout navy"><span class="navy tier2 tier2-green">Recall hook:</span> Hook.</div>'
            '<div class="nb"><strong>NB:</strong> <span class="tier2 tier2-teal">Footer term</span>.</div>'
        )
        self.assertEqual(summary["cards_with_tier2"], 1)
        self.assertEqual(summary["cards_with_tier2_in_both_paragraphs"], 1)
        self.assertEqual(summary["tier2_paragraph_1_spans"], 2)
        self.assertEqual(summary["tier2_paragraph_2_spans"], 1)
        self.assertEqual(summary["tier2_blue_spans"], 1)
        self.assertEqual(summary["tier2_red_spans"], 1)
        self.assertEqual(summary["tier2_lightblue_spans"], 1)
        self.assertEqual(summary["tier2_green_spans"], 0)
        self.assertEqual(summary["tier2_teal_spans"], 0)

    def test_inspection_accepts_zero_or_many_highlights_without_a_quota(self):
        no_highlights = self.inspect(
            "<p>First paragraph.</p><p>Second paragraph.</p>",
            deck_name="No Highlight Quota Zero",
        )
        many_highlights = self.inspect(
            '<p>' + " ".join(
                f'<span class="tier2 tier2-blue">term {index}</span>' for index in range(6)
            ) + "</p><p>Second paragraph.</p>",
            deck_name="No Highlight Quota Many",
        )
        self.assertEqual(no_highlights["cards_with_tier2"], 0)
        self.assertEqual(no_highlights["tier2_paragraph_1_spans"], 0)
        self.assertEqual(many_highlights["cards_with_tier2"], 1)
        self.assertEqual(many_highlights["tier2_paragraph_1_spans"], 6)
        self.assertEqual(many_highlights["tier2_blue_spans"], 6)
        self.assertEqual(many_highlights["tier2_paragraph_2_spans"], 0)

    def test_inspection_ignores_data_class_and_handles_quoted_gt_in_real_class_attribute(self):
        summary = self.inspect(
            '<p>First <span data-class="tier2 tier2-green">not a palette span</span>.'
            '<span title="x > y" class="tier2 tier2-blue">actual</span></p>'
            "<p>Second paragraph.</p>"
        )
        self.assertEqual(summary["tier2_blue_spans"], 1)
        self.assertEqual(summary["tier2_green_spans"], 0)

    def test_inspection_selects_two_meaningful_paragraphs(self):
        summary = self.inspect(
            '<p></p><p><span class="tier2 tier2-blue">first</span></p>'
            '<p><span class="tier2 tier2-red">second</span></p>'
        )
        self.assertEqual(summary["tier2_paragraph_1_spans"], 1)
        self.assertEqual(summary["tier2_paragraph_2_spans"], 1)
        self.assertEqual(summary["tier2_blue_spans"], 1)
        self.assertEqual(summary["tier2_red_spans"], 1)


class BudgetGuardTests(unittest.TestCase):
    @staticmethod
    def card(*, back=None, **overrides):
        card = {
            "front": "What condition defines pharmacokinetic steady state?",
            "back": back
            or (
                "<p>Pharmacokinetic <span class=\"key\">steady state</span> is the condition in which "
                "the average rate of drug input equals the average rate of drug elimination.</p>"
                "<p>Concentrations may continue to fluctuate within a dosing interval, "
                "but the pattern remains stable from one interval to the next.</p>"
            ),
            "recall_hook": {
                "color": "navy",
                "text": "Steady state represents balance between input and elimination."
            },
            "nb": {
                "mode": "actionable",
                "text": "In R, mrgsolve::mrgsim() can simulate concentration profiles under repeated dosing."
            },
        }
        card.update(overrides)
        return card

    def test_normalization_adds_recall_hook_and_nb_footer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir)
            spec = {
                "deck_name": "Normalized Mini Deck",
                "cards": [self.card()],
                "output_file": "normalized_mini_deck.apkg",
            }

            output_path, summary, cached = build_deck(spec, spec_dir)

            self.assertTrue(output_path.exists())
            self.assertFalse(cached)
            self.assertEqual(summary["cards"], 1)

    def test_normalization_rejects_missing_paragraph(self):
        with self.assertRaisesRegex(CardValidationError, "exactly two meaningful"):
            with tempfile.TemporaryDirectory() as tmpdir:
                build_deck(
                    {
                        "deck_name": "Invalid Mini Deck",
                        "cards": [self.card(back="<p>Only one paragraph.</p>")],
                    },
                    Path(tmpdir),
                )

    def test_normalization_rejects_unsupported_recall_color(self):
        with self.assertRaisesRegex(CardValidationError, "unsupported Recall hook color"):
            with tempfile.TemporaryDirectory() as tmpdir:
                build_deck(
                    {
                        "deck_name": "Invalid Color Deck",
                        "cards": [self.card(recall_hook={"color": "lightblue", "text": "Invalid recall color."})],
                    },
                    Path(tmpdir),
                )

    def test_not_applicable_nb_mode_is_rejected(self):
        card = self.card(
            nb={
                "mode": "not_applicable",
                "reason": "This definitional card has no direct computational operation.",
            }
        )
        with self.assertRaisesRegex(CardValidationError, "nb.mode must be 'actionable'"):
            normalize_card(card, deck_name="Noncomputational Mini Deck", card_index=1)

    def test_empty_actionable_nb_text_is_rejected(self):
        card = self.card(nb={"mode": "actionable", "text": "  "})
        with self.assertRaisesRegex(CardValidationError, "requires non-empty text"):
            normalize_card(card, deck_name="Invalid NB Deck", card_index=1)

    def test_legacy_nb_fallback_footer_is_rejected(self):
        card = self.card(
            back=(
                "<p>The concept is stated in the first paragraph.</p>"
                "<p>The second paragraph provides the required context.</p>"
                '<div class="nb"><strong>NB:</strong> Not applicable — this concept has no direct computational operation.</div>'
            )
        )
        card.pop("nb")
        with self.assertRaisesRegex(CardValidationError, "must be actionable"):
            normalize_card(card, deck_name="Legacy NB Deck", card_index=1)

    def test_all_recall_colors_are_allowed_without_restricting_tier2_palette(self):
        for color in ("blue", "red", "purple", "navy"):
            card = self.card(
                recall_hook={"color": color, "text": "This is a valid recall hook."},
                back=(
                    '<p><span class="key">Concept</span> is stated here.</p>'
                    "<p>The second paragraph provides the required context.</p>"
                    '<span class="tier2 tier2-lightblue">tier-two term</span>'
                ),
            )
            normalized = normalize_card(card, deck_name="Color Deck", card_index=1)
            self.assertIn(f'class="callout {color}"', normalized["back"])
            self.assertIn("tier2-lightblue", normalized["back"])

    def test_green_recall_hook_is_rejected_while_tier2_green_remains_valid(self):
        card = self.card(
            recall_hook={"color": "green", "text": "Green is no longer an approved Recall-hook color."},
            back=(
                "<p>The concept is stated in the first paragraph.</p>"
                "<p>The second paragraph provides the required context.</p>"
                '<span class="tier2 tier2-green">tier-two term</span>'
            ),
        )
        with self.assertRaisesRegex(CardValidationError, "unsupported Recall hook color"):
            normalize_card(card, deck_name="Color Deck", card_index=1)

    def test_build_preserves_tags_and_writes_anki_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir)
            spec = {
                "deck_name": "Tagged Mini Deck",
                "cards": [
                    {
                        **self.card(),
                        "tags": ["pk", "steady-state"],
                    }
                ],
                "output_file": "tagged_mini_deck.apkg",
            }

            output_path, summary, cached = build_deck(spec, spec_dir)

            self.assertTrue(output_path.exists())
            self.assertFalse(cached)
            self.assertEqual(summary["cards"], 1)
            self.assertEqual(summary["cards_with_key"], 1)

            import zipfile

            with zipfile.ZipFile(output_path) as package:
                self.assertIn("collection.anki2", package.namelist())

    def test_should_skip_creation_when_cache_signature_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir)
            output_path = spec_dir / "mini_deck.apkg"
            spec = {
                "deck_name": "Mini Deck",
                "cards": [self.card()],
                "output_file": str(output_path),
            }

            output_path, summary, cached = build_deck(spec, spec_dir)
            self.assertFalse(cached)
            self.assertTrue(output_path.exists())
            self.assertTrue(should_skip_creation(spec, spec_dir))

    def test_should_not_skip_creation_when_force_flag_asked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir)
            output_path = spec_dir / "mini_deck.apkg"
            spec = {
                "deck_name": "Mini Deck",
                "cards": [self.card()],
                "output_file": str(output_path),
            }

            build_deck(spec, spec_dir)
            self.assertFalse(should_skip_creation(spec, spec_dir, force=True))

    def test_rejects_cross_deck_duplicate_concepts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            primary_dir = root / "primary"
            other_dir = root / "other"
            primary_dir.mkdir()
            other_dir.mkdir()

            duplicate_front = "What does disposition mean after intravenous bolus dosing?"
            other_spec = {
                "deck_name": "Other Deck",
                "cards": [
                    {
                        "front": duplicate_front,
                        "back": "<p>Disposition is the combined process of distribution and elimination.</p>",
                    }
                ],
                "output_file": str(other_dir / "other.apkg"),
            }
            (other_dir / "other_spec.json").write_text(json.dumps(other_spec), encoding="utf-8")

            primary_spec = {
                "deck_name": "Primary Deck",
                "cards": [
                    {
                        "front": duplicate_front,
                        "back": "<p>Disposition is the combined process of distribution and elimination.</p>",
                    }
                ],
                "output_file": str(primary_dir / "primary.apkg"),
            }

            with self.assertRaises(ValueError):
                build_deck(primary_spec, primary_dir)


if __name__ == "__main__":
    unittest.main()
