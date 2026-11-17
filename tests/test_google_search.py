import io
import json
from unittest.mock import patch

from tools import google_search


def test_google_search_parses_results():
    fake_response = {
        "organic": [
            {
                "position": 1,
                "title": "Example Website",
                "link": "https://example.com",
                "snippet": "An example search result",
            }
        ],
        "peopleAlsoAsk": [{"question": "What is SEO?"}],
    }

    response_bytes = io.BytesIO(json.dumps(fake_response).encode("utf-8"))

    with (
        patch.dict("os.environ", {"SERPER_API_KEY": "test-key"}),
        patch("urllib.request.urlopen", return_value=response_bytes),
    ):
        result = google_search.invoke(
            {
                "query": "SEO tools",
                "num_results": 3,
            }
        )

    assert result["query"] == "SEO tools"
    assert len(result["organic"]) == 1
    assert result["organic"][0]["position"] == 1
    assert result["organic"][0]["title"] == "Example Website"
    assert result["peopleAlsoAsk"][0]["question"] == "What is SEO?"


from urllib.error import HTTPError
from unittest.mock import patch


def test_google_search_handles_http_error():
    error = HTTPError(
        url="https://google.serper.dev/search",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=None,
    )

    with (
        patch.dict("os.environ", {"SERPER_API_KEY": "test-key"}),
        patch("urllib.request.urlopen", side_effect=error),
    ):
        result = google_search.invoke({"query": "SEO tools"})

    assert "error" in result
    assert "429" in result["error"]
