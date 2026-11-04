from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

PALETTE: dict[str, str] = {
    "blue": "#255d8c",
    "red": "#b00000",
    "green": "#2e7d73",
    "gold": "#7bbddc",
    "pink": "#c65b7c",
    "orange": "#d9822b",
    "purple": "#7a4fb0",
    "teal": "#5aa6a1",
}

TIER2_VARIANTS: tuple[str, ...] = (
    "tier2-blue",
    "tier2-red",
    "tier2-green",
    "tier2-gold",
    "tier2-pink",
    "tier2-orange",
    "tier2-purple",
    "tier2-teal",
)


def p(text: str) -> str:
    return f"<p>{text}</p>"


def ul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def fig(src: str, caption: str) -> str:
    return f'<figure><img src="{src}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'


def callout(text: str, tone: str = "blue", label: str = "Recall hook:") -> str:
    normalized_tone = tone.casefold()
    if normalized_tone == "navy-blue":
        normalized_tone = "navy"
    if normalized_tone not in {"blue", "red", "purple", "navy"}:
        normalized_tone = "blue"
    return f'<div class="callout {normalized_tone}"><span class="{normalized_tone}">{label}</span> {text}</div>'


def memory_anchor(text: str, tone: str = "blue") -> str:
    return ""


def nb(text: str) -> str:
    return f'<div class="nb"><strong>NB:</strong> {text}</div>'


_NB_RULES: tuple[dict[str, Any], ...] = (
    {"family": "missingness", "terms": ("missing", "missingness", "incomplete data"), "tools": ("naniar::vis_miss()", "pandas.DataFrame.isna()", "SQL IS NULL"), "action": "visualize or summarize missing values"},
    {"family": "data-cleaning", "terms": ("data cleaning", "data entry", "questionnaire", "survey"), "tools": ("janitor::clean_names()", "pandas.DataFrame.rename()", "Power Query"), "action": "standardize field names and inspect malformed records"},
    {"family": "descriptive-statistics", "terms": ("mean", "median", "variance", "distribution", "descriptive"), "tools": ("numpy.mean()", "R summary()", "Excel PivotTable"), "action": "calculate and compare the relevant summary statistic"},
    {"family": "visualization", "terms": ("plot", "graph", "visualization", "trend", "contrast"), "tools": ("ggplot2", "seaborn", "Tableau"), "action": "visualize the stated comparison or trend"},
    {"family": "regression", "terms": ("regression", "linear model", "coefficient", "prediction"), "tools": ("statsmodels OLS", "R lm()", "SAS PROC REG"), "action": "fit the specified model and inspect its coefficients or predictions"},
    {"family": "causal-inference", "terms": ("causal", "confounding", "adjustment", "propensity", "instrumental variable"), "tools": ("Stata teffects", "MatchIt::matchit()", "Python linearmodels"), "action": "estimate the relevant adjusted contrast and inspect balance or assumptions"},
    {"family": "survival", "terms": ("survival", "censoring", "kaplan-meier", "time-to-event", "hazard"), "tools": ("SAS PROC LIFETEST", "lifelines KaplanMeierFitter", "survival::survfit()"), "action": "encode event time and censoring, then estimate or plot the survival curve"},
    {"family": "longitudinal", "terms": ("longitudinal", "repeated measures", "within-subject", "covariance structure"), "tools": ("nlme::gls()", "SAS PROC MIXED", "statsmodels MixedLM"), "action": "fit a repeated-measures model and inspect the within-subject covariance"},
    {"family": "simulation", "terms": ("simulation", "differential equation", "compartment", "stochastic"), "tools": ("Julia DifferentialEquations.jl", "deSolve::ode()", "scipy.integrate.solve_ivp()"), "action": "simulate the stated system and inspect its trajectory"},
    {"family": "database-query", "terms": ("database", "query", "cohort extraction", "record linkage"), "tools": ("PostgreSQL window functions", "dbt tests", "PySpark DataFrame API"), "action": "query or validate the records needed for the stated analysis"},
    {"family": "reproducibility", "terms": ("reproducibility", "workflow", "version control", "analysis pipeline"), "tools": ("Git", "Quarto", "GitHub Actions"), "action": "record and rerun the analysis steps reproducibly"},
)

CARD_TEMPLATES: dict[str, str] = {
    "paragraph_1": "Define the concept or state its model, mechanism, or procedure with necessary assumptions and notation.",
    "paragraph_2": "Add one distinct consequence, contrast, limitation, interpretation, or application.",
    "recall_hook": "Write one concise sentence that restates the central insight in fresh words; use only an approved hook color.",
    "nb": "Name one concrete ecosystem-specific operation and say what to run or inspect; keep it short and concept-specific.",
}


def infer_nb_rule(
    front: str,
    back: str,
    tags: list[str] | None = None,
    *,
    used_operations: set[str] | None = None,
) -> dict[str, Any] | None:
    haystack = " ".join([front, back, " ".join(tags or [])]).lower()
    for rule in _NB_RULES:
        if any(keyword_matches(haystack, term) for term in rule["terms"]):
            if used_operations is None or any(tool not in used_operations for tool in rule["tools"]):
                return rule
    return None


def infer_nb_text(front: str, back: str, tags: list[str] | None = None) -> str | None:
    """Return a short suggested NB; canonical deck export requires authored metadata."""
    rule = infer_nb_rule(front, back, tags)
    if rule is None:
        return None
    tool = rule["tools"][0]
    return f"Use {tool} to {rule['action']}."


def keyword_matches(haystack: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in haystack
    return re.search(rf"\b{re.escape(keyword)}\b", haystack) is not None


def _wrap_first_occurrence(text: str, phrase: str) -> str:
    if " " in phrase:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
    else:
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
    return pattern.sub(lambda match: f'<span class="key">{match.group(0)}</span>', text, count=1)


_HIGH_YIELD_RULES: list[tuple[set[str], tuple[str, ...]]] = [
    (
        {"time series", "airpassengers", "decomposition", "autocorrelation", "partial autocorrelation", "acf", "pacf", "forecast", "stationary", "trend", "seasonality"},
        ("time series", "AirPassengers", "decomposition", "autocorrelation", "partial autocorrelation", "ACF", "PACF", "forecast", "stationary", "trend", "seasonality"),
    ),
    (
        {"survival analysis", "survivor function", "survival function", "hazard function", "kaplan-meier", "kaplan meier", "censoring", "censored", "risk set", "median survival", "failure time"},
        ("survival analysis", "survivor function", "survival function", "hazard function", "Kaplan-Meier", "censoring", "censored", "risk set", "median survival", "failure time"),
    ),
    (
        {"right censoring", "left censoring", "interval censoring", "survival function", "event indicator", "time-to-event"},
        ("right censoring", "left censoring", "interval censoring", "survival function", "event indicator", "time-to-event", "survival time", "censored"),
    ),
    (
        {"population composition", "population structure", "population pyramids", "sex ratio", "sex imbalance", "age-dependency", "child-dependency", "old-age dependency"},
        ("population composition", "population structure", "population pyramids", "sex ratio", "age-dependency", "child-dependency", "old-age dependency", "sex imbalance"),
    ),
    (
        {"fecundity", "infecundity", "fecundability", "fertility", "natality", "natural fertility", "reproductivity", "gravidity", "parity", "birth interval", "pregnancy interval"},
        ("fecundity", "infecundity", "fecundability", "fertility", "natural fertility", "reproductivity", "gravidity", "parity", "birth interval", "pregnancy interval"),
    ),
    (
        {"crude birth rate", "cbr", "general fertility rate", "gfr", "age-specific fertility rate", "asfr", "total fertility rate", "tfr", "gross reproduction rate", "grr", "net reproduction rate", "nrr", "children ever born", "ceb", "replacement fertility", "population momentum"},
        ("crude birth rate", "general fertility rate", "age-specific fertility rate", "total fertility rate", "gross reproduction rate", "net reproduction rate", "children ever born", "replacement fertility", "population momentum", "cbr", "gfr", "asfr", "tfr", "grr", "nrr", "ceb"),
    ),
    (
        {"seasonal variation", "seasonal index", "simple averages method", "ratio to trend method", "percentage moving average method", "link relatives method"},
        ("seasonal variation", "seasonal index", "simple averages method", "ratio to trend method", "percentage moving average method", "link relatives method"),
    ),
    (
        {"non-compliance", "drop-ins", "recruitment", "retention", "phase i", "phase ii", "phase iii", "phase iv", "comparative effectiveness research", "cer", "propensity score matching", "instrumental variables"},
        ("non-compliance", "drop-ins", "recruitment", "retention", "Phase I", "Phase II", "Phase III", "Phase IV", "comparative effectiveness research", "propensity score matching", "instrumental variables"),
    ),
    (
        {"selection bias", "measurement bias", "reporting bias", "publication bias", "recall bias", "confounding bias", "causal inference"},
        ("selection bias", "measurement bias", "reporting bias", "publication bias", "recall bias", "confounding bias", "causal inference"),
    ),
    (
        {"sex ratio", "age", "median age", "mean age", "dependency ratio", "child-dependency ratio", "old-age dependency ratio"},
        ("sex ratio", "age", "median age", "mean age", "dependency ratio", "child-dependency ratio", "old-age dependency ratio"),
    ),
    (
        {"summary", "plot", "visualization", "forecasting", "package", "library", "ts_data"},
        ("summary", "plot", "visualization", "forecasting", "package", "library", "ts_data"),
    ),
]


_TITLE_RULES: list[tuple[set[str], tuple[str, ...]]] = [
    (
        {"time series"},
        ("time series", "AirPassengers", "autocorrelation", "partial autocorrelation", "ACF", "PACF", "forecast", "seasonality", "decomposition", "stationary"),
    ),
    (
        {"population composition", "population structure"},
        ("population composition", "population structure", "sex ratio", "population pyramids", "dependency ratio", "child-dependency ratio", "old-age dependency ratio"),
    ),
    (
        {"fertility", "measures and determinants"},
        ("fertility", "fecundity", "fecundability", "general fertility rate", "age-specific fertility rate", "total fertility rate", "gross reproduction rate", "net reproduction rate", "replacement fertility"),
    ),
    (
        {"survival analysis"},
        ("survival analysis", "censoring", "survival function", "hazard function", "Kaplan-Meier", "event indicator", "time-to-event", "median survival"),
    ),
    (
        {"infectious disease", "infectious diseases", "mathematical modeling", "sir", "seir", "compartmental", "epidemic", "pandemic", "outbreak"},
        ("infectious disease", "infectious diseases", "mathematical modeling", "SIR", "SEIR", "compartmental", "epidemic", "pandemic", "outbreak", "transmission", "recovery"),
    ),
    (
        {"force of infection", "density-dependent", "frequency-dependent", "mass-action", "proportionate mixing", "recovery", "infectious period"},
        ("force of infection", "density-dependent transmission", "frequency-dependent transmission", "mass-action transmission", "proportionate mixing", "recovery", "infectious period", "contact rate", "transmission rate"),
    ),
    (
        {"stationary", "stationarity", "autocovariance", "autocorrelation", "correlogram", "time series", "acf", "random walk", "seasonal"},
        ("stationary process", "stationarity", "autocovariance", "autocorrelation", "correlogram", "time series", "ACF", "random walk", "seasonal", "trend"),
    ),
    (
        {"autoregressive", "moving average", "arma", "arima", "airpassengers", "differencing", "time series models"},
        ("autoregressive", "moving average", "ARMA", "ARIMA", "AirPassengers", "differencing", "time series", "ACF", "PACF"),
    ),
    (
        {"moving average", "ma(1)", "ma(2)", "arma", "arima", "invertibility", "white noise", "residual"},
        ("moving average", "MA(1)", "MA(2)", "ARMA", "ARIMA", "invertibility", "white noise", "residual", "ACF"),
    ),
    (
        {"arima", "differences", "differencing", "stationary", "stationarity", "time series model selection"},
        ("ARIMA", "differencing", "stationary", "nonstationary", "stationarity", "trend", "auto.arima", "diff"),
    ),
    (
        {"design concepts iii", "clinical trials", "methods"},
        ("non-compliance", "drop-ins", "recruitment", "retention", "Phase I", "Phase II", "Phase III", "Phase IV", "comparative effectiveness research", "propensity score matching", "instrumental variables"),
    ),
]


def auto_highlight_key_terms(front: str, back: str, tags: list[str] | None = None, *, title: str | None = None) -> str:
    if "class=\"key\"" in back:
        return back

    haystack = " ".join([front, back, " ".join(tags or [])]).lower()
    title_haystack = (title or "").lower()

    for keywords, candidates in _TITLE_RULES:
        if title_haystack and any(keyword_matches(title_haystack, keyword) for keyword in keywords):
            for candidate in candidates:
                updated = _wrap_first_occurrence(back, candidate)
                if updated != back:
                    return updated

    for keywords, candidates in _HIGH_YIELD_RULES:
        if any(keyword_matches(haystack, keyword) for keyword in keywords):
            for candidate in candidates:
                updated = _wrap_first_occurrence(back, candidate)
                if updated != back:
                    return updated
    return back


def attach_nb_footnote(card: dict[str, Any]) -> dict[str, Any]:
    """Legacy authoring helper; the canonical builder never calls this fallback."""
    back = str(card.get("back", ""))
    updated = dict(card)
    if "class=\"nb\"" in back or "<strong>NB:</strong>" in back or "NB:" in back:
        return updated

    front = str(card.get("front", ""))
    tags = [str(tag) for tag in card.get("tags", [])]
    note = infer_nb_text(front, back, tags)
    if not note:
        return updated

    updated["back"] = back + nb(note)
    return updated


def tier2_variant_for(*parts: object) -> str:
    key = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha1(key.encode("utf-8")).digest()
    return TIER2_VARIANTS[digest[0] % len(TIER2_VARIANTS)]


def tier2(text: str, tone: str | None = None, *, seed: object | None = None) -> str:
    selected = tone or tier2_variant_for(seed if seed is not None else text)
    selected = selected.removeprefix("tier2-")
    return f'<span class="tier2 tier2-{selected}">{text}</span>'
