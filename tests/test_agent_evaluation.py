import pytest


@pytest.fixture
def seo_scenario():
    return {
        "page": "/best-running-shoes",
        "clicks": 5,
        "impressions": 1000,
        "ctr": 0.005,
        "position": 6.0,
    }


def evaluate_ctr_opportunity(data):
    """Evaluate whether a page meets a predefined CTR opportunity rule."""
    return data["impressions"] >= 500 and data["ctr"] < 0.02 and data["position"] <= 10


def test_detects_low_ctr_opportunity(seo_scenario):
    result = evaluate_ctr_opportunity(seo_scenario)

    assert result is True


def test_ctr_detection_precision_recall():
    scenarios = [
        {"impressions": 1000, "ctr": 0.005, "position": 6, "expected": True},
        {"impressions": 800, "ctr": 0.01, "position": 8, "expected": True},
        {"impressions": 100, "ctr": 0.005, "position": 5, "expected": False},
        {"impressions": 1200, "ctr": 0.08, "position": 4, "expected": False},
        {"impressions": 900, "ctr": 0.01, "position": 18, "expected": False},
    ]

    predictions = [evaluate_ctr_opportunity(scenario) for scenario in scenarios]

    tp = sum(
        predicted and scenario["expected"]
        for predicted, scenario in zip(predictions, scenarios)
    )
    fp = sum(
        predicted and not scenario["expected"]
        for predicted, scenario in zip(predictions, scenarios)
    )
    fn = sum(
        not predicted and scenario["expected"]
        for predicted, scenario in zip(predictions, scenarios)
    )

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0

    assert precision == 1.0
    assert recall == 1.0
