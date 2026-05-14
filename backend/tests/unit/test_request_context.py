"""Unit tests for Request Context."""

from backend.api.request_context import get_request_user_id, set_request_user_id

def test_request_context_lifecycle():
    # Initial state should be "system"
    assert get_request_user_id() == "system"
    
    # Set custom state
    set_request_user_id("test-user-123")
    assert get_request_user_id() == "test-user-123"
    
    # Reset
    set_request_user_id("system")
    assert get_request_user_id() == "system"
