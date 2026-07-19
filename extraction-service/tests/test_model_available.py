"""Regeneration must not depend on a job's stored model: `model_available`
classifies whether the CURRENT model is actually served. A 'model not found /
removed' error => unavailable (skip fast); any other error => transient (let the
normal retry path handle it). Pure — a fake provider, no network."""
from app.llm.factory import model_available


class _Provider:
    name = "fake"

    def __init__(self, exc):
        self.model = "test-model"
        self._exc = exc

    def complete_json(self, *a, **k):
        if self._exc:
            raise self._exc
        return "{}"


def test_reachable_model_is_available():
    assert model_available(_Provider(None)) is True


def test_404_not_found_is_unavailable():
    assert model_available(_Provider(Exception("404 page not found"))) is False
    assert model_available(_Provider(Exception("Error: model does not exist"))) is False
    assert model_available(_Provider(Exception("410 - Gone: model removed"))) is False


def test_transient_error_is_treated_as_available():
    # rate limits / timeouts / parse hiccups are NOT a model-availability signal
    assert model_available(_Provider(Exception("429 rate limit exceeded"))) is True
    assert model_available(_Provider(Exception("no JSON object found in response"))) is True
    assert model_available(_Provider(Exception("connection timeout"))) is True
