
# SEO Agent Evaluation

This directory contains the evaluation framework for
assessing the reliability of AI-generated SEO analyses.

## Evaluation Dimensions

1. Factual Accuracy
   - Are reported metrics consistent with source data?

2. Groundedness
   - Are analytical claims supported by tool outputs?

3. Actionability
   - Are recommendations specific and executable?

4. Uncertainty Calibration
   - Does the agent distinguish facts, hypotheses,
     and uncertain conclusions?

5. Hallucination Detection
   - Does the agent introduce unsupported claims?

## Methodology

Evaluation will use independently defined reference cases
and captured agent outputs.

Rule-based unit tests are not treated as evidence of
real-world agent accuracy.

## Status

Evaluation framework under development.
No validated benchmark scores are reported yet.
