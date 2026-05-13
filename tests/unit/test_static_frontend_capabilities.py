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

    assert "attachChatFiles($event)" in index_html
    assert "$refs.chatFileInput.click()" in index_html
    assert ":accept=\"chatFileAccept\"" in index_html
    assert "chatCanSend" in app_js
    assert "file.isImage?{type:'image_url'" in app_js
    assert "{type:'file',file:{file_data:file.url,filename:file.name,mime_type:file.mime}}" in app_js
    assert "selectedCaps.file_input" in app_js
    assert "file_input_mime_types" in app_js
    assert "chatFileUploadEnabled" in app_js
    assert "selectImageModel(m.id)" in index_html
    assert "x-model.number=\"imageCount\"" in index_html
    assert ":min=\"imageCountMin\"" in index_html
    assert ":max=\"imageCountMax\"" in index_html
    assert "imageCountHint" in index_html
    assert "imageResponseFormat" in index_html
    assert "imageGenerationMeta" in app_js
    assert "response_format:this.imageResponseFormat" in app_js
    assert "x-text=\"imageSize\"" in index_html
    assert "/v1/images/generations" in app_js
    assert "retryLastImage()" in index_html
    assert "downloadImage(item)" in index_html
    assert "retryImage(item)" in index_html
    assert "localStorage.getItem('aistudio.imageHistory')" in app_js
    assert "clearImageHistory()" in index_html
    assert "lightweightImageItem" in app_js
    assert "selectedHistoryItems" in app_js
    assert "downloadSelectedImages()" in index_html
    assert "deleteSelectedImages()" in index_html
    assert "deleteHistoryImage(item)" in index_html
    assert "imageHistorySelection" in app_js
    assert "sameOriginRequestPath" in app_js
    assert "explicit&&item?.path" in app_js
    assert "b64_json" not in app_js.split("return{id:item.id||path||url,url,path,delete_url:item.delete_url||url", 1)[1].split("}", 1)[0]


def test_static_frontend_custom_select_supports_keyboard_and_scrollable_image_menu():
    app_js = (ROOT / "src" / "aistudio_api" / "static" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "src" / "aistudio_api" / "static" / "index.html").read_text(encoding="utf-8")
    style_css = (ROOT / "src" / "aistudio_api" / "static" / "style.css").read_text(encoding="utf-8")

    assert "handleSelectKeydown" in app_js
    assert "ArrowDown" in app_js
    assert "Spacebar" in app_js
    assert "scrollIntoView({block:'nearest'})" in app_js
    assert "x-for=\"s in imageSizes\"" in index_html
    assert "aria-disabled=\"true\" x-show=\"!imageModels.length\"" in index_html
    assert "overscroll-behavior:contain" in style_css
    assert ".cselect-opt:hover,.cselect-opt.highlighted" in style_css
    assert ".image-form-panel{grid-row:span 2;position:sticky;top:20px;overflow:visible" in style_css