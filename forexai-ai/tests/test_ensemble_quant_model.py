"""Ensemble combination tests.

The ensemble is the only model the quant agent runs live, so its weighting,
probability reduction and agreement score need direct coverage. Member models
are injected fakes, so no ``.joblib`` artefacts are required.
"""

import pytest

from app.models.ensemble_quant_model import EnsembleQuantModel

from tests.fakes.fake_model import FakeQuantModel


def _model(name, **probabilities):
    return FakeQuantModel(name, probabilities)


def test_weights_are_normalised_to_sum_to_one():
    ensemble = EnsembleQuantModel(
        models=[_model("a", BUY=1.0), _model("b", BUY=1.0)],
        model_weights={"a": 3.0, "b": 1.0},
    )

    assert ensemble.model_weights == {"a": 0.75, "b": 0.25}


def test_equal_weights_when_none_supplied():
    ensemble = EnsembleQuantModel(
        models=[_model("a", BUY=1.0), _model("b", BUY=1.0)],
    )

    assert ensemble.model_weights == {"a": 0.5, "b": 0.5}


def test_missing_weight_for_a_member_raises():
    with pytest.raises(ValueError, match="Missing weights"):
        EnsembleQuantModel(
            models=[_model("a", BUY=1.0), _model("b", BUY=1.0)],
            model_weights={"a": 1.0},
        )


def test_probabilities_are_a_weighted_average():
    ensemble = EnsembleQuantModel(
        models=[
            _model("buyer", BUY=1.0),
            _model("seller", SELL=1.0),
        ],
        model_weights={"buyer": 0.5, "seller": 0.5},
    )

    probabilities = ensemble.predict_probabilities(None)

    assert probabilities["BUY"] == pytest.approx(0.5)
    assert probabilities["SELL"] == pytest.approx(0.5)
    assert probabilities["NO_TRADE"] == pytest.approx(0.0)


def test_predict_returns_the_highest_probability_direction():
    ensemble = EnsembleQuantModel(
        models=[_model("m1", BUY=0.7), _model("m2", BUY=0.6)],
    )

    prediction = ensemble.predict(None)

    assert prediction.direction == "BUY"
    assert prediction.probability == pytest.approx(0.65)
    assert prediction.model_agreement == pytest.approx(1.0)
    assert "ensemble(" in prediction.model_name


def test_agreement_drops_when_models_disagree():
    ensemble = EnsembleQuantModel(
        models=[_model("m1", BUY=0.9), _model("m2", SELL=0.9)],
    )

    prediction = ensemble.predict(None)

    assert prediction.model_agreement == pytest.approx(0.5)


def test_three_model_weighted_blend():
    ensemble = EnsembleQuantModel(
        models=[
            _model("random_forest", BUY=1.0),
            _model("xgboost", BUY=1.0),
            _model("logistic_regression", SELL=1.0),
        ],
        model_weights={
            "random_forest": 0.4,
            "xgboost": 0.4,
            "logistic_regression": 0.2,
        },
    )

    probabilities = ensemble.predict_probabilities(None)

    assert probabilities["BUY"] == pytest.approx(0.8)
    assert probabilities["SELL"] == pytest.approx(0.2)


def test_predict_runs_each_member_exactly_once():
    """Regression guard for SQA C-06.

    ``predict`` previously called each member's ``predict`` AND then
    ``predict_probabilities`` (which a SklearnQuantModel recomputes from
    scratch), so every member inferred twice per call. The single-pass refactor
    must invoke each member's probability path exactly once while producing the
    same direction/probability/agreement.
    """

    class _CountingModel(FakeQuantModel):
        def __init__(self, name, probabilities):
            super().__init__(name, probabilities)
            self.calls = 0

        def predict_probabilities(self, features):
            self.calls += 1
            return super().predict_probabilities(features)

        def predict(self, features):
            # A stray ``predict`` call is the bug we are guarding against.
            self.calls += 1
            return super().predict(features)

    m1 = _CountingModel("m1", {"BUY": 0.9})
    m2 = _CountingModel("m2", {"BUY": 0.6})

    ensemble = EnsembleQuantModel(models=[m1, m2])

    prediction = ensemble.predict(None)

    assert m1.calls == 1
    assert m2.calls == 1
    # Output is unchanged by the refactor.
    assert prediction.direction == "BUY"
    assert prediction.probability == pytest.approx(0.75)
    assert prediction.model_agreement == pytest.approx(1.0)


def test_predict_probabilities_runs_each_member_exactly_once():

    class _CountingModel(FakeQuantModel):
        def __init__(self, name, probabilities):
            super().__init__(name, probabilities)
            self.calls = 0

        def predict_probabilities(self, features):
            self.calls += 1
            return super().predict_probabilities(features)

    m1 = _CountingModel("m1", {"BUY": 1.0})
    m2 = _CountingModel("m2", {"BUY": 1.0})

    ensemble = EnsembleQuantModel(models=[m1, m2])

    ensemble.predict_probabilities(None)

    assert m1.calls == 1
    assert m2.calls == 1
