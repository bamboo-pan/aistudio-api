from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_static_frontend_uses_model_capabilities_for_controls():
    app_js = (ROOT / "src" / "aistudio_api" / "static" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "src" / "aistudio_api" / "static" / "index.html").read_text(encoding="utf-8")

    assert "selectedCaps" in app_js
    assert "applyModelCapabilities" in app_js
    assert "detail?.message" in app_js
    assert "d?.error?.message" in app_js
    assert "this.controlAvailable('search')&&this.cfg.search==='on'" in app_js
    assert "selectModel(m.id)" in index_html
    assert "controlAvailable('thinking')" in index_html
    assert "controlAvailable('stream')" in index_html


def test_static_frontend_exposes_account_health_tier_controls():
    app_js = (ROOT / "src" / "aistudio_api" / "static" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "src" / "aistudio_api" / "static" / "index.html").read_text(encoding="utf-8")

    assert "testAccount(a)" in index_html
    assert "updateTier(a,v)" in index_html
    assert "healthLabel(a.health_status)" in index_html
    assert "tierLabel(a.tier)" in index_html
    assert "/test`" in app_js
    assert "updateTier(a,tier)" in app_js


def test_static_frontend_exposes_image_upload_and_generation_page():
    app_js = (ROOT / "src" / "aistudio_api" / "static" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "src" / "aistudio_api" / "static" / "index.html").read_text(encoding="utf-8")

    assert "attachChatImages($event)" in index_html
    assert "$refs.chatFileInput.click()" in index_html
    assert "chatCanSend" in app_js
    assert "image_url:{url:img.url}" in app_js
    assert "selectedCaps.image_input" in app_js
    assert "selectImageModel(m.id)" in index_html
    assert "x-model.number=\"imageCount\"" in index_html
    assert "x-text=\"imageSize\"" in index_html
    assert "/v1/images/generations" in app_js
    assert "response_format:'url'" in app_js
    assert "retryLastImage()" in index_html
    assert "downloadImage(item)" in index_html
    assert "retryImage(item)" in index_html
    assert "localStorage.getItem('aistudio.imageHistory')" in app_js
    assert "clearImageHistory()" in index_html