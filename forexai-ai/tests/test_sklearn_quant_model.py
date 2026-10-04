"""Inference contract of the sklearn-backed quant model.

The real artefacts are large, git-ignored ``.joblib`` files, so the estimator is
injected here. The valuable behaviour is the mapping from the estimator's class
probabilities to the SELL / NO_TRADE / BUY vocabulary the API exposes.
"""

from app.models.sklearn_quant_model import SklearnQuantModel


class _FakeEstimator:
    def __init__(self, probabilities):
        self._probabilities = probabilities

    def predict_proba(self, features):
        return [self._probabilities]


def _model(probabilities):
    # Bypass __init__ so the test does not need a joblib artefact on disk.
    model = SklearnQuantModel.__new__(SklearnQuantModel)
    model.model = _FakeEstimator(probabilities)
    model.model_name = "test-model"
    model.model_path = None
    return model


def test_probability_indices_map_to_directions():
    probabilities = _model([0.2, 0.3, 0.5]).predict_probabilities(None)

    assert probabilities == {"SELL": 0.2, "NO_TRADE": 0.3, "BUY": 0.5}


def test_predict_returns_the_argmax_direction():
    prediction = _model([0.1, 0.2, 0.7]).predict(None)

    assert prediction.direction == "BUY"
    assert prediction.probability == 0.7
    assert prediction.model_name == "test-model"


def test_predict_can_return_no_trade():
    prediction = _model([0.2, 0.6, 0.2]).predict(None)

    assert prediction.direction == "NO_TRADE"
