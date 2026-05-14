"""Unit tests for API schemas."""

from datetime import date
import pytest
from pydantic import ValidationError
from backend.api.schemas.schemas import EventFilterRequest

def test_event_filter_request_defaults():
    req = EventFilterRequest()
    assert req.limit == 1000
    assert req.start_date is None
    assert req.end_date is None

def test_event_filter_request_valid():
    req = EventFilterRequest(
        start_date=date(2024, 1, 1),
        country_code="US",
        limit=50
    )
    assert req.start_date == date(2024, 1, 1)
    assert req.country_code == "US"
    assert req.limit == 50

def test_event_filter_request_limit_bounds():
    with pytest.raises(ValidationError):
        EventFilterRequest(limit=0)
        
    with pytest.raises(ValidationError):
        EventFilterRequest(limit=200_000)

def test_event_filter_request_country_code_length():
    with pytest.raises(ValidationError):
        EventFilterRequest(country_code="USA_TOO_LONG")
