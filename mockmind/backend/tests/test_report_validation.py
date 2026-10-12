import pytest

from backend.services.report_generator import validate_report

GOOD = {
    "overall_score": "7.5",
    "hiring_recommendation": "yes",
    "category_scores": {"technical": 7, "communication": 8},
}


def test_valid_report_is_normalized():
    r = validate_report(dict(GOOD))
    assert r["overall_score"] == 7.5
    assert r["strengths"] == [] and r["question_feedback"] == [] and r["summary"] == ""


@pytest.mark.parametrize("missing", ["overall_score", "hiring_recommendation", "category_scores"])
def test_missing_required_key_rejected(missing):
    bad = dict(GOOD)
    del bad[missing]
    with pytest.raises(ValueError):
        validate_report(bad)


def test_unknown_recommendation_rejected():
    # The report page indexes a config map by this value; an unknown one used to crash it.
    with pytest.raises(ValueError):
        validate_report({**GOOD, "hiring_recommendation": "definitely"})


def test_non_object_rejected():
    with pytest.raises(ValueError):
        validate_report(["not", "an", "object"])
