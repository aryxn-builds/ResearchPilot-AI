"""Tests for Pydantic API schemas — validation boundaries."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.common import make_paginated, make_success
from app.schemas.research import ResearchConfig, ResearchRequest
from app.schemas.users import UpdateUserRequest

# ── ResearchRequest ──────────────────────────────────────────────────────────


def test_research_request_valid() -> None:
    """Valid research question passes validation."""
    req = ResearchRequest(
        question="What are the long-term effects of sleep deprivation on cognition?"
    )
    assert req.question.startswith("What")


def test_research_request_strips_whitespace() -> None:
    """Question is stripped of leading/trailing whitespace."""
    req = ResearchRequest(question="   What is quantum entanglement?   ")
    assert not req.question.startswith(" ")
    assert not req.question.endswith(" ")


def test_research_request_rejects_blank_question() -> None:
    """Blank question (whitespace only) is rejected."""
    with pytest.raises(ValidationError):
        ResearchRequest(question="   ")


def test_research_request_rejects_too_short() -> None:
    """Question shorter than 10 chars is rejected."""
    with pytest.raises(ValidationError):
        ResearchRequest(question="Too short")


def test_research_request_rejects_too_long() -> None:
    """Question over 1000 chars is rejected."""
    with pytest.raises(ValidationError):
        ResearchRequest(question="x" * 1001)


def test_research_config_defaults() -> None:
    """ResearchConfig provides correct defaults."""
    config = ResearchConfig()
    assert config.max_iterations == 2
    assert config.source_types == ["web"]
    assert config.max_sources_per_task == 5


def test_research_config_max_iterations_cap() -> None:
    """max_iterations cannot exceed 3."""
    with pytest.raises(ValidationError):
        ResearchConfig(max_iterations=4)


def test_research_config_min_iterations() -> None:
    """max_iterations cannot be 0."""
    with pytest.raises(ValidationError):
        ResearchConfig(max_iterations=0)


# ── UpdateUserRequest ────────────────────────────────────────────────────────


def test_update_user_all_optional() -> None:
    """UpdateUserRequest accepts empty body (all fields optional)."""
    req = UpdateUserRequest()
    assert req.display_name is None
    assert req.preferences is None


def test_update_user_display_name_min_length() -> None:
    """display_name must not be empty string."""
    with pytest.raises(ValidationError):
        UpdateUserRequest(display_name="")


# ── Common schemas ───────────────────────────────────────────────────────────


def test_make_success_wraps_data() -> None:
    """make_success wraps data in SuccessResponse envelope."""
    result = make_success({"key": "value"})
    assert result.data == {"key": "value"}
    assert result.meta is not None
    assert result.meta.request_id is not None


def test_make_paginated_calculates_total_pages() -> None:
    """make_paginated computes total_pages correctly."""
    result = make_paginated(data=["a", "b", "c"], page=1, page_size=2, total=5)
    assert result.meta.pagination.total_pages == 3  # ceil(5/2)
    assert result.meta.pagination.total == 5
    assert len(result.data) == 3


def test_make_paginated_zero_results() -> None:
    """make_paginated handles zero total gracefully."""
    result = make_paginated(data=[], page=1, page_size=20, total=0)
    assert result.meta.pagination.total_pages == 0
    assert result.data == []
