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
    assert "testAccount(a)" in app_js
    assert "/test`" in app_js
    assert "updateTier(a,tier)" in app_js


def test_static_frontend_exposes_exhaustion_mode_and_resolution_usage():
    app_js = (ROOT / "src" / "aistudio_api" / "static" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "src" / "aistudio_api" / "static" / "index.html").read_text(encoding="utf-8")
    style_css = (ROOT / "src" / "aistudio_api" / "static" / "style.css").read_text(encoding="utf-8")

    assert "exhaustion" in app_js
    assert "耗尽模式" in app_js
    assert "['exhaustion','round_robin','lru','least_rl']" in index_html
    assert "rotationHint(rotCfg.mode)" in index_html
    assert "imageSizeEntries(a)" in index_html
    assert "accountImageSizeTotals" in app_js
    assert "statsTotals" in app_js
    assert "model-stats-panel" in index_html
    assert "totalReqs" in index_html
    assert "totalRL" in index_html
    assert "go('dashboard')" not in index_html
    assert "view==='dashboard'" not in index_html
    assert "if(route==='dashboard'){this.go('accounts');return}" in app_js
    assert "['chat','images','dashboard','accounts']" not in app_js
    assert "image_sizes" in app_js
    assert "resolution-chip" in index_html
    assert ".rotation-option.active" in style_css
    assert ".resolution-chip" in style_css
    assert ".model-stats-panel" in style_css


def test_static_frontend_exposes_image_upload_and_generation_page():
    app_js = (ROOT / "src" / "aistudio_api" / "static" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "src" / "aistudio_api" / "static" / "index.html").read_text(encoding="utf-8")
    style_css = (ROOT / "src" / "aistudio_api" / "static" / "style.css").read_text(encoding="utf-8")

    assert "attachChatFiles($event)" in index_html
    assert "$refs.chatFileInput.click()" in index_html
    assert ":accept=\"chatFileAccept\"" in index_html
    assert "chatCanSend" in app_js
    assert "file.isImage?{type:'image_url'" in app_js
    assert "{type:'file',file:{file_data:file.url,filename:file.name,mime_type:file.mime}}" in app_js
    assert "selectedCaps.file_input" in app_js
    assert "file_input_mime_types" in app_js
    assert "chatFileUploadEnabled" in app_js
    assert "applyRouteHash" in app_js
    assert "hashchange" in app_js
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
    assert "attachImageReferences($event)" in index_html
    assert "imageEditReferences" in app_js
    assert "imageRequestImages" in app_js
    assert "body.images=images" in app_js
    assert "setBaseImage(item)" in index_html
    assert "pinImageReference(item,'history')" in index_html
    assert "pinImageReference(item,'result')" in index_html
    assert "pinSelectedHistory()" in index_html
    assert "clearImageEditSession()" in index_html
    assert "imageConversation" in app_js
    assert "imageSessions:[]" in app_js
    assert "activeImageSessionId" in app_js
    assert "loadImageSessions()" in app_js
    assert "loadImageSessions(false)" in app_js
    assert "saveCurrentImageSession(prompt)" in app_js
    assert "this.imagePrompt=''" in app_js
    assert "this.imageResults=[]" in app_js
    assert "fetchJson('/image-sessions')" in app_js
    assert "`/image-sessions/${encodeURIComponent(this.activeImageSessionId)}`" in app_js
    assert "restoreImageSession(session)" in app_js
    assert "deleteImageSession(session)" in app_js
    assert "imagePreview:null" in app_js
    assert "openImagePreview(item)" in app_js
    assert "closeImagePreview()" in app_js
    assert "@click=\"openImagePreview(item)\"" in index_html
    assert "@keydown.escape.window=\"closeImagePreview()\"" in index_html
    assert "image-preview-overlay" in index_html
    assert "会话历史" in index_html
    assert "已保存会话" in index_html
    assert "imageSessions.length" in index_html
    assert "restoreImageSession(session)" in index_html
    assert "deleteImageSession(session)" in index_html
    assert "image-session-history" in style_css
    assert "image-session-card" in style_css
    assert ".image-thumb img{width:100%;height:100%;object-fit:contain" in style_css
    assert ".image-preview-img{max-width:100%;max-height:100%;object-fit:contain" in style_css
    assert "编辑会话" in index_html
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
    assert "引导式 Studio" in index_html
    assert "image-studio-compose" in index_html
    assert "imageSubmitHint" in app_js
    assert "imageRunSummary" in app_js
    assert ".image-form-panel{grid-row:span 3;position:relative;overflow:visible" in style_css
    assert ".image-studio-controls{grid-template-columns:1fr 1fr" in style_css
    assert "position:sticky" not in style_css.split("/* Image generation */", 1)[1].split("/* Toast */", 1)[0]
    assert "@media(max-width:960px)" in style_css