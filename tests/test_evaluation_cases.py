import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evaluation" / "cases.json"


def test_evaluation_cases_are_valid():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    assert "cases" in data
    assert len(data["cases"]) > 0

    for case in data["cases"]:
        assert case["id"]
        assert case["category"]
        assert case["input"]
        assert case["expected"]


def test_ranking_interpretation_reference():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    case = next(c for c in data["cases"] if c["id"] == "SERP-001")

    position = case["input"]["average_position"]

    assert position == 4.8
    assert case["expected"]["is_first_page"] is True
    assert case["expected"]["interpretation"] == "approximately fifth position"


import re


def detect_invalid_claims(agent_response, invalid_claims):
    """Detect incorrect SERP page interpretations."""
    normalized = re.sub(r"\s+", " ", agent_response.lower())

    # Expand shorthand expressions such as page-four/five.
    normalized = re.sub(
        r"\bpage[- ](four|five)/(?P<second>four|five)\b",
        lambda match: (f"page-{match.group(1)} " f"page-{match.group('second')}"),
        normalized,
    )

    return [
        claim
        for claim in invalid_claims
        if re.search(
            r"(?<!\w)" + re.escape(claim.lower()) + r"(?!\w)",
            normalized,
        )
    ]


def test_detects_real_agent_ranking_error():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    case = next(c for c in data["cases"] if c["id"] == "SERP-001")

    agent_response = (
        "A page-four/five ranking with near-zero CTR "
        "strongly suggests a weak SERP snippet."
    )

    # The known incorrect interpretation should be detected.
    invalid_claims = case["invalid_claims"] + [
        "page-four",
        "page-five",
    ]

    detected = detect_invalid_claims(agent_response, invalid_claims)

    assert "page-four" in detected
    assert "page-five" in detected


def test_accepts_correct_ranking_interpretation():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    case = next(c for c in data["cases"] if c["id"] == "SERP-001")

    agent_response = (
        "An average position of 4.8 means the result "
        "appears around the fifth position on average."
    )

    detected = detect_invalid_claims(
        agent_response,
        case["invalid_claims"],
    )

    assert detected == []
