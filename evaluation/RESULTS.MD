
# SEO Agent Evaluation Results

## Evaluation Setup

A qualitative before-and-after evaluation was conducted
using SEO analysis reports generated for the same
30-day Search Console reporting period.

The evaluation focused on:
- Ranking interpretation
- Evidence-grounded recommendations
- Separation of observations and hypotheses
- Uncertainty communication
- Actionability

## Findings

| Criterion | Initial Output | Revised Output |
|---|---|---|
| Ranking interpretation | Known error | Correct in reviewed examples |
| Observation vs. hypothesis | Inconsistent | Clearly separated |
| Uncertainty communication | Limited | Improved |
| Actionable recommendations | Present | Present with clearer caveats |
| Data limitations | Partially addressed | Explicitly addressed |

## Identified Error

The initial report incorrectly described an average
position of 4.8 as a "page-four/five ranking".

A regression test was added to detect this specific
error pattern.

## Improvements

The system prompt was updated to:
- Clarify Google Search Console average position
- Distinguish observations from hypotheses
- Require explicit uncertainty statements
- Avoid unsupported causal conclusions

## Limitations

This is a qualitative case study, not a statistically
validated benchmark.

The reviewed outputs were not evaluated against a
complete independent ground-truth dataset.

No general accuracy or hallucination-rate claims
are made.
