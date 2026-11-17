from tools import difference


def test_difference_calculates_metric_changes():
    current = {
        "clicks": 150,
        "impressions": 2000,
        "ctr": 0.075,
        "position": 5.0,
    }

    previous = {
        "clicks": 100,
        "impressions": 1600,
        "ctr": 0.0625,
        "position": 7.0,
    }

    result = difference(current, previous)

    assert result["clicks"] == 50
    assert result["impressions"] == 400
    assert result["ctr"] == 0.0125
    assert result["position"] == -2.0
