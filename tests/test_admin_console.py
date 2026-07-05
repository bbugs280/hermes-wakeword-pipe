"""
PiHermes Admin Console — Playwright E2E Tests
Tests the Hermes dashboard with PiHermes plugin tab.
SSH tunnel required: ssh -L 9119:localhost:9119 beets3d@hermes-pi
Run: python -m pytest tests/test_admin_console.py -v --browser=chromium -s
"""

import pytest
from playwright.sync_api import expect, Page


BASE = "http://localhost:9119"


@pytest.fixture()
def page(browser):
    """Fresh page per test."""
    page = browser.new_page()
    yield page
    page.close()


# ── Test 1: Dashboard loads and has content ──

def test_dashboard_loads(page: Page):
    """Dashboard should load and render content beyond just a blank shell."""
    page.goto(BASE, timeout=15000)
    # Wait for React hydration
    page.wait_for_timeout(3000)
    body_text = page.locator("body").inner_text()
    print(f"\n  Body text ({len(body_text)} chars): {body_text[:200]}...")

    # A functioning dashboard has either:
    # - Navigation tabs/links
    # - A header/logo
    # - Some interactive elements
    assert len(body_text) > 50, f"Dashboard appears empty ({len(body_text)} chars)"


# ── Test 2: Dashboard has navigation/sidebar ──

def test_dashboard_has_navigation(page: Page):
    """Dashboard should have clickable navigation elements."""
    page.goto(BASE, timeout=15000)
    page.wait_for_timeout(3000)
    links = page.locator("a, button, [role=tab], [role=link]").count()
    print(f"\n  Interactive elements (links/buttons/tabs): {links}")
    assert links > 0, "No interactive elements found"


# ── Test 3: PiHermes API status endpoint ──

def test_pihermes_api_status(page: Page):
    """PiHermes plugin API /status should be accessible."""
    response = page.request.get(f"{BASE}/api/plugins/pihermes/status")
    print(f"\n  /status: HTTP {response.status}")
    # 401 means endpoint exists but needs auth — that's acceptable
    # 200 means it's working unauthenticated
    # 404 means the endpoint doesn't exist at all
    assert response.status != 404, "PiHermes API endpoint /status not found (404)"


# ── Test 4: PiHermes API restart endpoint ──

def test_pihermes_api_restart(page: Page):
    """PiHermes plugin API /restart should exist."""
    response = page.request.post(f"{BASE}/api/plugins/pihermes/restart")
    print(f"\n  /restart: HTTP {response.status}")
    assert response.status != 404, "PiHermes API endpoint /restart not found (404)"


# ── Test 5: Other bundled plugins are visible ──

def test_bundled_plugins_visible(page: Page):
    """Bundled plugins (hermes-achievements, kanban) should be discoverable."""
    # Check if the hermes-achievements API is mounted
    response = page.request.get(f"{BASE}/api/plugins/hermes-achievements/status")
    kanban_resp = page.request.get(f"{BASE}/api/plugins/kanban/boards")
    print(f"\n  hermes-achievements: HTTP {response.status}")
    print(f"  kanban: HTTP {kanban_resp.status}")
    # At least one should exist (not 404)
    assert not (response.status == 404 and kanban_resp.status == 404), (
        "No bundled plugin APIs found — dashboard may not have loaded plugins"
    )


# ── Test 6: Dashboard resources load without errors ──

def test_dashboard_no_console_errors(page: Page):
    """Dashboard should not have JavaScript console errors."""
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(BASE, timeout=15000)
    page.wait_for_timeout(4000)
    print(f"\n  Console errors ({len(errors)}): {errors[:5]}")

    # Filter out non-critical errors (favicon 404s, 401 auth on API calls)
    critical_errors = [e for e in errors if "favicon" not in e.lower() 
                       and "404" not in e and "401" not in e and "Unauthorized" not in e]
    assert len(critical_errors) == 0, f"Critical console errors: {critical_errors[:3]}"


# ── Test 7: PiHermes tab or plugin is discoverable ──

def test_pihermes_plugin_discoverable(page: Page):
    """The word 'PiHermes' or 'pihermes' should appear in dashboard source."""
    page.goto(BASE, timeout=15000)
    page.wait_for_timeout(3000)
    html = page.content()
    body_text = page.locator("body").inner_text().lower()
    print(f"\n  'pihermes' in HTML: {'pihermes' in html.lower()}")
    print(f"  'pihermes' in body text: {'pihermes' in body_text}")
    print(f"  Body text sample: {body_text[:300]}")
    # Ideally pihermes appears — if not, the plugin isn't loading
    assert (
        "pihermes" in html.lower() or "pihermes" in body_text
    ), "PiHermes plugin not found in dashboard — not loading"
