import json
import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

from anki_deck_builder import (
    DEFAULT_CSS,
    CardValidationError,
    build_deck,
    build_signature,
    cache_path_for,
    inspect_spec,
    main,
    normalize_card,
    should_skip_creation,
    tier2_colors_by_paragraph,
)
from deck_spec_helpers import PALETTE, auto_highlight_key_terms, tier2


class AuthoringPaletteContractTests(unittest.TestCase):
    DOC_NAMES = (
        "ANKI_CARD_GENERATION_PROMPT.md",
        "DECK_SPEC_TEMPLATE.md",
        "README.md",
        "SKILL.md",
    )
    PALETTE_NAMES = ("blue", "red", "green", "lightblue", "pink", "orange", "purple", "teal")
    COLOR_ROLES = {
        "| blue | anchor concept |",
        "| purple | contrast or second concept |",
        "| orange | condition, constraint, or design point |",
        "| green | added factor or consequence |",
        "| teal | time-course or procedural detail |",
        "| red | limiting or cautionary mechanism |",
        "| pink | transition or shape marker |",
        "| lightblue | notation, symbol, or named statistic |",
    }

    @classmethod
    def authoring_paths(cls):
        root = Path(__file__).parent
        return [root / name for name in cls.DOC_NAMES] + [
            root.parent / "skills" / "anki-deck-generation" / "SKILL.md"
        ]

    def test_authoring_docs_require_both_paragraphs_and_canonical_palette(self):
        for path in self.authoring_paths():
            with self.subTest(document=path.name, path=path):
                raw_content = path.read_text(encoding="utf-8").casefold()
                content = " ".join(raw_content.split())
                self.assertIn("lightblue", content)
                self.assertIn("#7bbddc", content)
                self.assertIn("exactly two", content)
                self.assertRegex(content, r"2–3 (?:complete )?sentences")
                self.assertIn("400–550", content)
                self.assertRegex(content, r"2–4 (?:tier-2 )?spans in paragraph 1")
                self.assertRegex(content, r"2–3 (?:spans )?in paragraph 2")
                self.assertIn("1–4-word noun phrases", content)
                self.assertIn("at least two core colors", content)
                self.assertIn("at most one span per secondary color", content)
                mentioned_colors = set(re.findall(r"\btier2-([a-z]+)\b", content)) - {"color"}
                self.assertEqual(mentioned_colors, set(self.PALETTE_NAMES), "the authoring palette must be exactly the eight supported colors")
                for color in self.PALETTE_NAMES:
                    self.assertIn(color, content)
                self.assertTrue(self.COLOR_ROLES.issubset({line.strip() for line in raw_content.splitlines()}))
                self.assertNotIn("tier2-gold", content)
                self.assertNotIn(".key", content)
                self.assertNotRegex(content, r"bold[- ]red|answer[- ]target|answer target")

    def test_authoring_prompt_requires_authored_tier2_and_explains_density(self):
        prompt_source = (Path(__file__).parent / "ANKI_CARD_GENERATION_PROMPT.md").read_text(encoding="utf-8")
        reusable_prompt = re.search(r"````text\n(.*?)\n````", prompt_source, re.DOTALL)
        self.assertIsNotNone(reusable_prompt, "the complete reusable prompt must be enclosed in a four-backtick fence")
        prompt = " ".join(reusable_prompt.group(1).casefold().split())
        self.assertIn("2–4 tier-2 spans in paragraph 1 and 2–3 in paragraph 2", prompt)
        self.assertIn("400–550 visible characters", prompt)
        self.assertIn("2–3 complete sentences per paragraph", prompt)
        self.assertIn("never leave either paragraph unhighlighted", prompt)
        self.assertIn("never nest tier-2 spans", prompt)
        self.assertIn("never repeat a highlighted phrase within a card", prompt)
        self.assertIn("not in the recall hook or nb metadata", prompt)
        self.assertIn("when spans are removed, the prose must remain grammatical", prompt)
        self.assertIn("before returning the cards, perform this editorial check", prompt)

    def test_authoring_prompt_demonstrates_valid_tier2_markup(self):
        prompt = (Path(__file__).parent / "ANKI_CARD_GENERATION_PROMPT.md").read_text(encoding="utf-8")
        match = re.search(r"Preferred PHM4510 example.*?```html\n(.*?)```", prompt, re.DOTALL)
        self.assertIsNotNone(match, "a preferred PHM4510-derived HTML example is required")
        example = match.group(1)
        self.assertIn("population-average concentration–response curve", example)
        paragraphs = re.findall(r"<p>(.*?)</p>", example, re.DOTALL)
        self.assertEqual(len(paragraphs), 2)
        all_colors = []
        total_visible_chars = 0
        for paragraph in paragraphs:
            spans = re.findall(r"<span\b([^>]*)>(.*?)</span>", paragraph, re.DOTALL)
            self.assertGreaterEqual(len(spans), 2)
            self.assertLessEqual(len(spans), 4 if paragraph is paragraphs[0] else 3)
            self.assertEqual(paragraph.count("<span"), len(spans), "every opening span must be closed and inspected")
            plain = re.sub(r"<[^>]+>", "", paragraph)
            total_visible_chars += len(plain)
            self.assertGreaterEqual(len(plain), 200)
            self.assertLessEqual(len(plain), 275)
            self.assertGreaterEqual(len(re.findall(r"[.!?](?=\s|$)", plain)), 2)
            self.assertLessEqual(len(re.findall(r"[.!?](?=\s|$)", plain)), 3)
            for attributes, body in spans:
                class_match = re.search(r'\bclass="([^"]*)"', attributes)
                self.assertIsNotNone(class_match, "every example span must declare its class list")
                class_list = class_match.group(1)
                self.assertRegex(class_list, r"^tier2 tier2-[a-z]+$")
                color = class_list.removeprefix("tier2 tier2-")
                self.assertIn(color, self.PALETTE_NAMES)
                self.assertNotIn("<span", body)
                self.assertGreaterEqual(len(body.split()), 1)
                self.assertLessEqual(len(body.split()), 4)
                all_colors.append(color)
        self.assertGreaterEqual(total_visible_chars, 400)
        self.assertLessEqual(total_visible_chars, 550)
        self.assertGreaterEqual(len(all_colors), 4)
        self.assertLessEqual(len(all_colors), 7)
        self.assertGreaterEqual(len(set(all_colors) & {"blue", "purple", "orange", "green"}), 2)

    def test_template_does_not_offer_noncanonical_highlighting_classes(self):
        template = (Path(__file__).parent / "DECK_SPEC_TEMPLATE.md").read_text(encoding="utf-8")
        self.assertNotIn(".key", template)
        self.assertNotIn("or equivalent", template.casefold())
        self.assertIn('<span class="tier2 tier2-{color}">', template)


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
        summary = self.inspect(Tier2DensityContractTests.VALID_BACK)
        self.assertEqual(summary["cards_with_tier2"], 1)
        self.assertEqual(summary["cards_with_tier2_in_both_paragraphs"], 1)
        self.assertEqual(summary["tier2_paragraph_1_spans"], 3)
        self.assertEqual(summary["tier2_paragraph_2_spans"], 2)
        self.assertEqual(summary["tier2_blue_spans"], 1)
        self.assertEqual(summary["tier2_red_spans"], 0)
        self.assertEqual(summary["tier2_lightblue_spans"], 1)
        self.assertEqual(summary["tier2_green_spans"], 1)
        self.assertEqual(summary["tier2_teal_spans"], 0)

    def test_inspection_rejects_zero_or_excessive_highlights(self):
        no_highlights = re.sub(r'<span class="tier2 tier2-[a-z]+">(.*?)</span>', r'\1', Tier2DensityContractTests.VALID_BACK)
        with self.assertRaisesRegex(CardValidationError, "paragraph 1 must contain 2–4 Tier-2 spans"):
            self.inspect(no_highlights)
        six_in_p1 = Tier2DensityContractTests.VALID_BACK.replace(
            '</p><p>',
            '<span class="tier2 tier2-blue">extra one</span> <span class="tier2 tier2-purple">extra two</span> <span class="tier2 tier2-orange">extra three</span></p><p>',
            1,
        )
        with self.assertRaisesRegex(CardValidationError, "paragraph 1 must contain 2–4 Tier-2 spans"):
            self.inspect(six_in_p1)

    def test_inspection_ignores_data_class_and_handles_quoted_gt_in_real_class_attribute(self):
        back = Tier2DensityContractTests.VALID_BACK.replace(
            '<span class="tier2 tier2-blue">conditional mean</span>',
            '<span data-class="tier2 tier2-green" title="x > y" class="tier2 tier2-blue">conditional mean</span>',
        )
        paragraph_colors = tier2_colors_by_paragraph(back)
        self.assertEqual(paragraph_colors[0].count("blue"), 1)
        self.assertEqual(paragraph_colors[0].count("green"), 0)

    def test_inspection_rejects_tier2_spans_outside_answer_paragraphs(self):
        with self.assertRaisesRegex(CardValidationError, "Tier-2 spans must appear only in the two answer paragraphs"):
            self.inspect(Tier2DensityContractTests.VALID_BACK + '<span class="tier2 tier2-teal">outside</span>')


class BudgetGuardTests(unittest.TestCase):
    @staticmethod
    def card(*, back=None, **overrides):
        card = {
            "front": "What condition defines pharmacokinetic steady state?",
            "back": back or Tier2DensityContractTests.VALID_BACK,
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
            self.assertEqual(summary["cards_with_key"], 0)

            import zipfile

            with zipfile.ZipFile(output_path) as package:
                self.assertIn("collection.anki2", package.namelist())


class Tier2DensityContractTests(unittest.TestCase):
    VALID_BACK = (
        '<p>For specified predictor values, multiple regression estimates the '
        '<span class="tier2 tier2-blue">conditional mean</span> of the response. '
        'The <span class="tier2 tier2-purple">βᵢ coefficient</span> gives the average '
        'response change per unit increase in its predictor while the '
        '<span class="tier2 tier2-orange">other predictors</span> are held fixed.</p>'
        '<p>The fitted mean supports comparisons across covariate settings and can '
        'reveal adjusted associations. This interpretation depends on the '
        '<span class="tier2 tier2-green">model assumptions</span>; the '
        '<span class="tier2 tier2-lightblue">βᵢ estimate</span> describes a '
        'population-average relationship, not a guaranteed response for one individual.</p>'
    )

    @classmethod
    def card(cls, back=None):
        return {
            "front": "How does multiple regression interpret a fitted response?",
            "back": back or cls.VALID_BACK,
            "recall_hook": {"color": "navy", "text": "The fitted equation summarizes an adjusted mean relationship."},
            "nb": {"mode": "actionable", "text": "In R, lm() fits the specified multiple regression model."},
        }

    @classmethod
    def inspect(cls, back=None, *, spec_dir=None):
        spec = {"deck_name": "Density Test Deck", "cards": [cls.card(back)]}
        if spec_dir is None:
            with tempfile.TemporaryDirectory() as tmpdir:
                return inspect_spec(spec, Path(tmpdir))
        return inspect_spec(spec, Path(spec_dir))

    def test_valid_card_reports_visible_length_paragraph_counts_and_color_counts(self):
        summary = self.inspect()
        card = summary["card_metrics"][0]
        self.assertEqual(card["card"], 1)
        self.assertEqual(card["visible_chars"], 492)
        self.assertEqual(card["p1_spans"], 3)
        self.assertEqual(card["p2_spans"], 2)
        self.assertEqual(card["colors"]["blue"], 1)
        self.assertEqual(card["colors"]["purple"], 1)
        self.assertEqual(card["colors"]["orange"], 1)
        self.assertEqual(card["colors"]["green"], 1)
        self.assertEqual(card["colors"]["lightblue"], 1)

    def test_rejects_visible_prose_below_and_above_contract(self):
        short = (
            '<p>The <span class="tier2 tier2-blue">conditional mean</span> changes with predictors. '
            'The <span class="tier2 tier2-purple">βᵢ coefficient</span> estimates average response change '
            'while <span class="tier2 tier2-orange">other predictors</span> remain fixed.</p>'
            '<p>The <span class="tier2 tier2-green">model assumptions</span> constrain inference. '
            'The <span class="tier2 tier2-lightblue">βᵢ estimate</span> describes a population mean.</p>'
        )
        long = self.VALID_BACK.replace(
            "one individual.</p>",
            ("one individual, while careful interpretation is needed across every relevant covariate setting " * 2) + ".</p>",
        )
        for back in (short, long):
            with self.subTest(visible_chars=len(re.sub(r"<[^>]+>", "", back))):
                with self.assertRaisesRegex(CardValidationError, "visible prose must be 400–550 characters"):
                    self.inspect(back)

    def test_rejects_paragraph_outside_200_to_275_visible_characters(self):
        imbalanced = (
            '<p>The <span class="tier2 tier2-blue">conditional mean</span> is estimated from predictors. '
            'The <span class="tier2 tier2-purple">βᵢ coefficient</span> gives change while '
            '<span class="tier2 tier2-orange">other predictors</span> stay fixed.</p>'
            '<p>The fitted mean supports comparisons across covariate settings and can reveal adjusted associations. '
            'This interpretation depends on the <span class="tier2 tier2-green">model assumptions</span>; '
            'the <span class="tier2 tier2-lightblue">βᵢ estimate</span> describes a population-average relationship, '
            'not a guaranteed response for one individual, and extrapolation beyond observed covariate ranges requires caution.</p>'
        )
        self.assertTrue(400 <= len(re.sub(r"<[^>]+>", "", imbalanced)) <= 550)
        with self.assertRaisesRegex(CardValidationError, "paragraph 1 visible prose must be 200–275 characters"):
            self.inspect(imbalanced)

    def test_rejects_paragraph_sentence_count_outside_two_or_three(self):
        back = self.VALID_BACK.replace(
            "response. The <span class=\"tier2 tier2-purple\">βᵢ coefficient</span>",
            "response, while the <span class=\"tier2 tier2-purple\">βᵢ coefficient</span>",
            1,
        )
        with self.assertRaisesRegex(CardValidationError, "paragraph 1 must contain 2–3 sentences"):
            self.inspect(back)

    def test_rejects_paragraph_span_counts_outside_contract(self):
        back = self.VALID_BACK.replace('<span class="tier2 tier2-purple">', '<span class="tier2 tier2-purple">', 1)
        back = back.replace('</span> gives the average', '</span> gives the average', 1)
        # Removing two complete P1 spans leaves one, while preserving the surrounding prose.
        back = back.replace('<span class="tier2 tier2-blue">conditional mean</span>', 'conditional mean')
        back = back.replace('<span class="tier2 tier2-orange">other predictors</span>', 'other predictors')
        with self.assertRaisesRegex(CardValidationError, "paragraph 1 must contain 2–4 Tier-2 spans"):
            self.inspect(back)

    def test_rejects_nested_tier2_spans(self):
        back = self.VALID_BACK.replace(
            '<span class="tier2 tier2-blue">conditional mean</span>',
            '<span class="tier2 tier2-blue">conditional <span class="tier2 tier2-teal">mean</span></span>',
        )
        with self.assertRaisesRegex(CardValidationError, "Tier-2 spans must not be nested"):
            self.inspect(back)

    def test_rejects_key_answer_markup(self):
        back = self.VALID_BACK.replace(
            'class="tier2 tier2-blue"', 'class="key tier2 tier2-blue"', 1
        )
        with self.assertRaisesRegex(CardValidationError, "key markup is not permitted"):
            self.inspect(back)

    def test_rejects_tier2_spans_in_recall_hook_or_nb(self):
        for suffix in (
            '<div class="callout navy"><span class="tier2 tier2-teal">hook term</span></div>',
            '<div class="nb"><strong>NB:</strong> <span class="tier2 tier2-teal">NB term</span></div>',
        ):
            with self.subTest(suffix=suffix):
                with self.assertRaisesRegex(CardValidationError, "Tier-2 spans must appear only in the two answer paragraphs"):
                    self.inspect(self.VALID_BACK + suffix)

    def test_rejects_spans_longer_than_four_words(self):
        back = self.VALID_BACK.replace(
            'other predictors</span>', 'all remaining explanatory predictor variables</span>'
        )
        with self.assertRaisesRegex(CardValidationError, "Tier-2 span must contain 1–4 words"):
            self.inspect(back)

    def test_rejects_duplicate_span_phrases_within_a_card(self):
        back = self.VALID_BACK.replace('βᵢ coefficient</span>', 'conditional mean</span>')
        with self.assertRaisesRegex(CardValidationError, "Tier-2 phrase is repeated within the card"):
            self.inspect(back)

    def test_requires_two_core_colors_and_caps_secondary_colors(self):
        only_blue = re.sub(r'tier2-(?:purple|orange|green|lightblue)', 'tier2-blue', self.VALID_BACK)
        with self.assertRaisesRegex(CardValidationError, "at least two core Tier-2 colors"):
            self.inspect(only_blue)

        duplicate_teal = self.VALID_BACK.replace('tier2-green', 'tier2-teal').replace('tier2-lightblue', 'tier2-teal')
        with self.assertRaisesRegex(CardValidationError, "secondary Tier-2 color 'teal' may appear at most once"):
            self.inspect(duplicate_teal)

    def test_check_mode_validates_spec_even_when_cache_is_current(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir)
            spec = {"deck_name": "Check Contract Deck", "cards": [self.card(self.VALID_BACK[:-10])]}
            spec_path = spec_dir / "deck_spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            output = spec_dir / "deck.apkg"
            output.write_text("cached", encoding="utf-8")
            cache_path_for(output).write_text(
                json.dumps({"signature": build_signature(spec, spec_dir)}),
                encoding="utf-8",
            )
            with mock.patch.object(sys, "argv", ["anki_deck_builder.py", "--spec", str(spec_path), "--check"]):
                with self.assertRaisesRegex(CardValidationError, "back must contain exactly two meaningful"):
                    main()

    def test_cli_reports_visible_length_paragraph_counts_and_each_color(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_dir = Path(tmpdir)
            spec_path = spec_dir / "deck_spec.json"
            spec = {"deck_name": "Report Deck", "cards": [self.card(self.VALID_BACK)]}
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", ["anki_deck_builder.py", "--spec", str(spec_path)]):
                with redirect_stdout(stdout):
                    self.assertEqual(main(), 0)
            report = stdout.getvalue()
            self.assertIn("Card 1: visible 492 chars; P1 3 spans; P2 2 spans", report)
            self.assertIn("colors: blue 1, red 0, green 1, lightblue 1, pink 0, orange 1, purple 1, teal 0", report)

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
