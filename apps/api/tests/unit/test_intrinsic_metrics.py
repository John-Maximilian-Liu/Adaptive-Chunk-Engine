"""Unit tests for Adaptive-Chunking-style intrinsic metrics."""
from evaluation_engine.intrinsic_metrics import score_chunks, compute_size_compliance


def test_size_compliance_bounds():
    ok = ["word " * 80]
    assert compute_size_compliance(ok, min_tokens=10, max_tokens=500) == 1.0
    bad = ["tiny"]
    assert compute_size_compliance(bad, min_tokens=50, max_tokens=100) == 0.0


def test_score_chunks_produces_all_metrics():
    text = (
        "Alpha introduces the policy. It requires review.\n\n"
        "Beta continues the argument. They must approve changes.\n\n"
        "Gamma closes with appendix references."
    )
    chunks = [
        "Alpha introduces the policy. It requires review.",
        "Beta continues the argument. They must approve changes.",
        "Gamma closes with appendix references.",
    ]
    score = score_chunks(chunks, text, min_tokens=1, max_tokens=500)
    assert score.sc is not None and 0 <= score.sc <= 1
    assert score.icc is not None
    assert score.dcc is not None
    assert score.bi is not None
    assert score.rc is not None
    assert score.mean is not None
    pct = score.as_percent_dict()
    assert "Mean" in pct
