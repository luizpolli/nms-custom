from app.services.assurance import clamp_score, severity_penalty


def test_severity_penalty_caps_occurrences():
    assert severity_penalty("critical", 10) == 200
    assert severity_penalty("major", 2) == 50
    assert severity_penalty("unknown", 1) == 3


def test_clamp_score_bounds_values():
    assert clamp_score(105) == 100
    assert clamp_score(-4) == 0
    assert clamp_score(87.6) == 88
