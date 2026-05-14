"""Unit tests for the application factory."""

from backend.api.main import create_app

def test_create_app():
    app = create_app()
    assert app is not None
    assert app.title == "GNIEM — Global News Intelligence & Event Monitoring"
    
    # Check that routers are mounted
    routes = [getattr(r, "path", "") for r in app.routes]
    assert any("health" in p for p in routes)
    assert any("events" in p for p in routes)
    assert any("analytics" in p for p in routes)
    assert any("map" in p for p in routes)
