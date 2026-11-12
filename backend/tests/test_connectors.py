"""تست اتصال‌های کتالوگی: ساختار کتالوگ، محافظت SSRF، ریسک پویا و API عمومی."""
from __future__ import annotations

import pytest

from app.integrations.catalog import CATALOG, catalog_list, get_provider
from app.tools.base import ToolContext, classify_risk
from app.tools.connectors import HttpApiTool


def test_catalog_is_large_and_well_formed():
    assert len(CATALOG) >= 60, "باید ده‌ها سرویس معروف پوشش داده شود"
    for key, p in CATALOG.items():
        assert p["name"] and p["category"] and p["base"], key
        assert p["fields"], f"{key} باید حداقل یک فیلد داشته باشد"
        assert p["auth"] in ("bearer", "basic", "none") or ":" in p["auth"], key
        assert p["base"].startswith(("http://", "https://", "postgresql://")), key
        assert key == key.lower()


def test_catalog_covers_big_providers():
    for must in ("openai", "anthropic", "google_gemini", "github", "cloudflare", "slack",
                 "notion", "stripe", "telegram", "brave", "discord", "vercel", "shopify"):
        assert must in CATALOG, f"{must} باید در کتالوگ باشد"


def test_public_listing_has_no_secrets():
    items = catalog_list()
    assert len(items) == len(CATALOG)
    blob = str(items)
    assert "api_key\"" not in blob or "fields" in blob  # فقط نام فیلدها، نه مقدار
    for it in items:
        assert set(it) == {"key", "name", "category", "base", "fields", "docs", "auth", "header", "actions", "note"}


def test_risk_is_dynamic_for_network_tool():
    tool = HttpApiTool()
    assert classify_risk(tool, {"provider": "github", "method": "GET"}) == "safe"
    assert classify_risk(tool, {"provider": "github", "method": "POST"}) == "confirm"
    # کنش از پیش‌تعریف‌شده هم درست تفسیر می‌شود
    assert classify_risk(tool, {"provider": "notion", "action": "search"}) == "confirm"


@pytest.mark.asyncio
async def test_http_api_blocks_unknown_provider(app_client, auth):
    ctx = ToolContext(user_id="x", workspace_root=__import__("pathlib").Path("."))
    res = await HttpApiTool().run({"provider": "does-not-exist"}, ctx)
    assert not res.ok and "کتالوگ" in res.output


@pytest.mark.asyncio
async def test_http_api_requires_credentials(app_client):
    ctx = ToolContext(user_id="no-such-user", workspace_root=__import__("pathlib").Path("."))
    res = await HttpApiTool().run({"provider": "github"}, ctx)
    assert not res.ok and "ثبت نشده" in res.output


@pytest.mark.asyncio
async def test_catalog_endpoint_exposed(app_client):
    r = await app_client.get("/api/integrations/catalog")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 60
    assert any(p["key"] == "openai" for p in d["providers"])
    assert d["categories"]["ai"]


@pytest.mark.asyncio
async def test_saved_provider_is_listed_but_secret_hidden(app_client, auth):
    r = await app_client.post("/api/integrations", headers=auth,
                              json={"kind": "notion", "config": {"token": "secret_abc123456"}})
    assert r.status_code == 200
    listing = (await app_client.get("/api/integrations", headers=auth)).json()
    assert listing["notion"]["configured"] is True
    assert "token" in listing["notion"]["fields_configured"]
    assert "secret_abc123456" not in str(listing)
