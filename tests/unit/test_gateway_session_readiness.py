import json

import pytest

from aistudio_api.config import settings
from aistudio_api.infrastructure.account import tier_detector
from aistudio_api.infrastructure.account.tier_detector import AccountTier, TierResult
from aistudio_api.infrastructure.gateway.session import AI_STUDIO_URL, AI_STUDIO_URL_FALLBACK, BrowserSession


class FakeRequest:
    def __init__(self, url: str, post_data: str, headers: dict[str, str]):
        self.url = url
        self.post_data = post_data
        self.headers = headers


class FakeRoute:
    def __init__(self, request: FakeRequest):
        self.request = request
        self.aborted = False
        self.continued = False

    def abort(self):
        self.aborted = True

    def continue_(self):
        self.continued = True


class FakeTextArea:
    def __init__(self, page: "FakePage"):
        self.page = page

    def fill(self, value: str):
        if self.page.redirect_on_next_fill:
            self.page.redirect_on_next_fill = False
            self.page.url = "https://ai.google.dev/gemini-api/docs/available-regions"
            self.page.has_default_makersuite = False
            self.page.has_textarea = False
            raise RuntimeError("Element is not attached to the DOM")
        self.page.filled_texts.append(value)


class FakeButton:
    def __init__(self, page: "FakePage"):
        self.page = page

    def click(self):
        self.page.clicks += 1
        self.page.trigger_generate_content_request()


class FakePage:
    def __init__(
        self,
        url: str = "about:blank",
        *,
        has_default_makersuite: bool = False,
        has_textarea: bool = False,
        title: str = "AI Studio",
        body: str = "",
        ready_after_waits: int | None = None,
        install_results: list[str] | None = None,
        goto_redirect_url: str | None = None,
        goto_error: Exception | None = None,
        redirect_on_next_fill: bool = False,
    ):
        self.url = url
        self.has_default_makersuite = has_default_makersuite
        self.has_textarea = has_textarea
        self.title_text = title
        self.body = body
        self.ready_after_waits = ready_after_waits
        self.install_results = list(install_results or [])
        self.goto_redirect_url = goto_redirect_url
        self.goto_error = goto_error
        self.redirect_on_next_fill = redirect_on_next_fill
        self.goto_urls: list[str] = []
        self.wait_calls: list[int] = []
        self.filled_texts: list[str] = []
        self.clicks = 0
        self.route_handlers: list[tuple[str, object]] = []
        self.unroute_calls: list[str] = []
        self.routed_requests: list[FakeRoute] = []
        self.generate_content_body = json.dumps(
            ["gemini-3-flash-preview", {"payload": "x" * 120}, None, None, "snapshot"],
            ensure_ascii=False,
        )
        self.generate_content_headers = {"authorization": "Bearer token", "content-type": "application/json"}

    def goto(self, url: str, **kwargs):
        self.url = self.goto_redirect_url or url
        self.goto_urls.append(url)
        if self.goto_error is not None:
            raise self.goto_error

    def wait_for_timeout(self, timeout_ms: int):
        self.wait_calls.append(timeout_ms)
        if self.ready_after_waits is not None and len(self.wait_calls) >= self.ready_after_waits:
            self.has_default_makersuite = True
            self.has_textarea = True

    def evaluate(self, script: str, *args):
        if "__bg_hooked" in script and "snapKey" in script:
            return self.install_results.pop(0) if self.install_results else "hooked:snapshotKey"
        if "window.default_MakerSuite" in script:
            return self.has_default_makersuite
        if "document.body" in script:
            return self.body
        return None

    def query_selector(self, selector: str):
        if selector == "textarea" and self.has_textarea:
            return FakeTextArea(self)
        if selector == "button:has-text('Run')":
            return FakeButton(self)
        return None

    def title(self):
        return self.title_text

    def route(self, pattern: str, handler):
        self.route_handlers.append((pattern, handler))

    def unroute(self, pattern: str, handler):
        self.unroute_calls.append(pattern)
        self.route_handlers = [(p, h) for p, h in self.route_handlers if p != pattern or h is not handler]

    def trigger_generate_content_request(self):
        request = FakeRequest(
            "https://aistudio.google.com/_/BardChatUi/data/batchexecute/GenerateContent",
            self.generate_content_body,
            self.generate_content_headers,
        )
        route = FakeRoute(request)
        self.routed_requests.append(route)
        for _, handler in list(self.route_handlers):
            handler(route)


class BrowserSessionForTest(BrowserSession):
    def __init__(self, page: FakePage):
        super().__init__(port=0)
        self._hook_page = page
        self.goto_calls = 0
        self.install_calls = 0

    def _ensure_browser_sync(self):
        return object()

    def _goto_aistudio_sync(self, page) -> None:
        self.goto_calls += 1
        page.url = AI_STUDIO_URL
        page.has_default_makersuite = True
        page.has_textarea = True

    def _install_hooks_sync(self, page) -> None:
        self.install_calls += 1


class FakeTierContext:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeTierBrowser:
    def __init__(self):
        self.storage_states = []
        self.contexts = []

    def new_context(self, **kwargs):
        self.storage_states.append(kwargs.get("storage_state"))
        context = FakeTierContext()
        self.contexts.append(context)
        return context


class TierDetectionSessionForTest(BrowserSession):
    def __init__(self):
        super().__init__(port=0)
        self.browser = FakeTierBrowser()
        self.ensure_process_calls = 0

    def _ensure_browser_process_sync(self):
        self.ensure_process_calls += 1
        self._browser = self.browser
        return self.browser

    def _ensure_browser_sync(self):
        raise AssertionError("tier detection for an explicit auth file must not preheat the active browser context")


class TemplateCaptureSessionForTest(BrowserSessionForTest):
    def __init__(self, page: FakePage):
        super().__init__(page)
        self.wait_until_idle_calls = 0

    def _ensure_botguard_service_sync(self):
        return self._hook_page

    def _wait_until_idle_sync(self, page) -> None:
        self.wait_until_idle_calls += 1


def test_chat_url_detection_requires_aistudio_chat_route():
    session = BrowserSession(port=0)

    assert session._is_aistudio_chat_url("https://aistudio.google.com/prompts/new_chat")
    assert session._is_aistudio_chat_url("https://aistudio.google.com/app/prompts/new_chat")
    assert session._is_aistudio_chat_url("https://aistudio.google.com/prompts/abc123")
    assert not session._is_aistudio_chat_url("https://aistudio.google.com/app/apikey")
    assert not session._is_aistudio_chat_url("https://accounts.google.com/signin")


def test_ensure_hook_page_navigates_wrong_aistudio_route_before_install():
    page = FakePage(url="https://aistudio.google.com/app/apikey")
    session = BrowserSessionForTest(page)

    assert session._ensure_hook_page_sync() is page

    assert session.goto_calls == 1
    assert session.install_calls == 1


def test_ensure_hook_page_reuses_ready_chat_route():
    page = FakePage(url=AI_STUDIO_URL, has_default_makersuite=True, has_textarea=True)
    session = BrowserSessionForTest(page)

    assert session._ensure_hook_page_sync() is page

    assert session.goto_calls == 0
    assert session.install_calls == 1


def test_goto_waits_until_chat_runtime_and_input_are_ready():
    page = FakePage(ready_after_waits=2)
    session = BrowserSession(port=0)

    session._goto_aistudio_sync(page)

    assert page.goto_urls == [AI_STUDIO_URL]
    assert page.has_default_makersuite is True
    assert page.has_textarea is True


def test_goto_recovers_from_ai_developers_docs_redirect():
    page = FakePage(title="Available regions", body="Google AI for Developers")

    def goto(url: str, **kwargs):
        page.goto_urls.append(url)
        if len(page.goto_urls) == 1:
            page.url = "https://ai.google.dev/gemini-api/docs/available-regions"
            return
        page.url = url
        page.has_default_makersuite = True
        page.has_textarea = True

    page.goto = goto
    session = BrowserSession(port=0)

    session._goto_aistudio_sync(page)

    assert page.goto_urls[:2] == [AI_STUDIO_URL, AI_STUDIO_URL_FALLBACK]
    assert page.url == AI_STUDIO_URL_FALLBACK


def test_goto_failure_reports_readiness_diagnostics():
    page = FakePage(title="Account page", body="Login completed but chat shell is missing")
    session = BrowserSession(port=0)

    with pytest.raises(RuntimeError) as exc_info:
        session._goto_aistudio_sync(page)

    message = str(exc_info.value)
    assert "AI Studio chat runtime not ready" in message
    assert "url=https://aistudio.google.com/" in message
    assert "title=Account page" in message
    assert "default_MakerSuite=False" in message
    assert "textarea=False" in message
    assert "body=Login completed but chat shell is missing" in message


def test_goto_google_signin_reports_auth_state_diagnostics(tmp_path):
    auth_file = tmp_path / "missing-auth.json"
    page = FakePage(
        title="Sign in - Google Accounts",
        body="Sign in Use your Google Account",
        goto_redirect_url="https://accounts.google.com/v3/signin/identifier?continue=https%3A%2F%2Faistudio.google.com",
    )
    session = BrowserSession(port=0)
    session._auth_file = str(auth_file)

    with pytest.raises(RuntimeError) as exc_info:
        session._goto_aistudio_sync(page)

    message = str(exc_info.value)
    assert "AI Studio redirected to Google sign-in" in message
    assert "browser auth state is missing or invalid" in message
    assert f"auth_file={auth_file}" in message
    assert "exists=False" in message
    assert "title=Sign in - Google Accounts" in message
    assert "body=Sign in Use your Google Account" in message


def test_goto_google_signin_after_navigation_error_reports_auth_state(tmp_path):
    auth_file = tmp_path / "missing-auth.json"
    page = FakePage(
        title="Sign in - Google Accounts",
        body="Sign in Use your Google Account",
        goto_redirect_url="https://accounts.google.com/v3/signin/identifier?continue=https%3A%2F%2Faistudio.google.com",
        goto_error=TimeoutError("navigation timed out"),
    )
    session = BrowserSession(port=0)
    session._auth_file = str(auth_file)

    with pytest.raises(RuntimeError) as exc_info:
        session._goto_aistudio_sync(page)

    message = str(exc_info.value)
    assert "AI Studio redirected to Google sign-in" in message
    assert "browser auth state is missing or invalid" in message
    assert "navigation timed out" not in message
    assert f"auth_file={auth_file}" in message
    assert "exists=False" in message


def test_new_context_missing_auth_file_fails_before_unauthenticated_context(tmp_path):
    session = BrowserSession(port=0)
    session._auth_file = str(tmp_path / "missing-auth.json")
    session._browser = object()

    with pytest.raises(FileNotFoundError) as exc_info:
        session._new_context_sync()

    assert "Browser auth state file is missing" in str(exc_info.value)


def test_browser_options_set_proxy_identity_when_proxy_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "proxy_server", "http://127.0.0.1:7890")
    session = BrowserSession(port=0)

    options = session._browser_options_sync()

    assert options["proxy"] == {"server": "http://127.0.0.1:7890"}
    assert options["locale"] == settings.camoufox_locale
    assert options["config"]["timezone"] == settings.camoufox_timezone
    assert options["config"]["geolocation:latitude"] == settings.camoufox_geolocation_latitude
    assert options["config"]["geolocation:longitude"] == settings.camoufox_geolocation_longitude
    assert options["i_know_what_im_doing"] is True


def test_install_hook_failure_reports_page_diagnostics():
    page = FakePage(
        url=AI_STUDIO_URL,
        has_textarea=True,
        title="AI Studio Chat",
        body="Chat shell visible without runtime",
        install_results=["no_default_MakerSuite"] * 4,
    )
    session = BrowserSession(port=0)

    with pytest.raises(RuntimeError) as exc_info:
        session._install_hooks_sync(page)

    message = str(exc_info.value)
    assert "Hook install failed: no_default_MakerSuite" in message
    assert f"url={AI_STUDIO_URL}" in message
    assert "title=AI Studio Chat" in message
    assert "default_MakerSuite=False" in message
    assert "textarea=True" in message
    assert "body=Chat shell visible without runtime" in message


def test_detect_tier_for_auth_file_does_not_require_active_auth(monkeypatch):
    session = TierDetectionSessionForTest()

    def fake_detect_tier_sync(context, timeout_ms):
        assert timeout_ms == 12345
        return TierResult(tier=AccountTier.PRO, email="user@example.com", raw_header="user@example.com PRO")

    monkeypatch.setattr(tier_detector, "detect_tier_sync", fake_detect_tier_sync)

    result = session._detect_tier_for_auth_file_sync("/tmp/auth.json", timeout_ms=12345)

    assert result.tier == AccountTier.PRO
    assert session.ensure_process_calls == 1
    assert session.browser.storage_states == ["/tmp/auth.json"]
    assert session.browser.contexts[0].closed is True


class FakeOnboardingPage:
    def __init__(self, results):
        self.results = list(results)
        self.wait_calls = []

    def evaluate(self, script: str, *args):
        assert "google apis terms" in script.lower()
        return self.results.pop(0) if self.results else {"needed": False}

    def wait_for_timeout(self, timeout_ms: int):
        self.wait_calls.append(timeout_ms)


class FakeImageOnboardingPage:
    def __init__(self, *, initial_consent: bool = False):
        self.wait_calls = []
        self.evaluate_calls = []
        self.initial_consent = initial_consent
        self.consent_calls = 0
        self.trigger_calls = 0

    def evaluate(self, script: str, *args):
        self.evaluate_calls.append(script)
        if "image_entry_not_found" in script:
            self.trigger_calls += 1
            if self.initial_consent and self.trigger_calls == 1:
                return {"triggered": False, "reason": "already_visible"}
            return {"triggered": True, "label": "image Image Generation"}
        if "model_card_not_found" in script:
            return {"selected": True, "label": "Nano Banana Pro"}
        if "google apis terms" in script.lower():
            self.consent_calls += 1
            if self.initial_consent and self.consent_calls == 1:
                return {"needed": True, "checked": True, "submitted": False, "remaining": True}
            if self.initial_consent and self.consent_calls == 2:
                return {"needed": True, "checked": False, "submitted": True, "remaining": False}
            return {"needed": False, "checked": False, "submitted": False, "remaining": False}
        return None

    def wait_for_timeout(self, timeout_ms: int):
        self.wait_calls.append(timeout_ms)


def test_aistudio_onboarding_completion_clicks_required_consent_until_submitted():
    page = FakeOnboardingPage([
        {"needed": True, "checked": True, "submitted": False, "remaining": True},
        {"needed": True, "checked": False, "submitted": True, "remaining": False},
    ])
    session = BrowserSession(port=0)

    assert session._complete_aistudio_onboarding_sync(page) is True

    assert page.wait_calls == [1200, 1200]


def test_aistudio_onboarding_completion_noops_when_not_needed():
    page = FakeOnboardingPage([{"needed": False, "checked": False, "submitted": False, "remaining": False}])
    session = BrowserSession(port=0)

    assert session._complete_aistudio_onboarding_sync(page) is False

    assert page.wait_calls == []


def test_image_model_capture_prepares_image_onboarding(monkeypatch):
    page = FakeImageOnboardingPage()
    session = BrowserSession(port=0)

    assert session._prepare_model_onboarding_sync(page, "gemini-3-pro-image-preview") is True

    assert page.wait_calls == [1200, 1200]
    assert any("model_card_not_found" in script for script in page.evaluate_calls)


def test_image_model_capture_reopens_image_entry_after_initial_terms():
    page = FakeImageOnboardingPage(initial_consent=True)
    session = BrowserSession(port=0)

    assert session._prepare_model_onboarding_sync(page, "gemini-3-pro-image-preview") is True

    assert page.trigger_calls == 1
    assert page.consent_calls >= 2
    assert any("model_card_not_found" in script for script in page.evaluate_calls)


def test_text_model_capture_skips_image_onboarding():
    page = FakeImageOnboardingPage()
    session = BrowserSession(port=0)

    assert session._prepare_model_onboarding_sync(page, "gemini-3-flash-preview") is False
    assert page.evaluate_calls == []


class TemplateCaptureImageSessionForTest(TemplateCaptureSessionForTest):
    def __init__(self, page):
        super().__init__(page)
        self.ensure_hook_calls = 0
        self.botguard_calls = 0
        self.prepare_calls = []
        self.install_calls = 0
        self.goto_calls = 0

    def _ensure_hook_page_sync(self):
        self.ensure_hook_calls += 1
        return self._hook_page

    def _ensure_botguard_service_sync(self):
        self.botguard_calls += 1
        return self._hook_page

    def _prepare_model_onboarding_sync(self, page, model: str) -> bool:
        self.prepare_calls.append((page, model, self.botguard_calls))
        return "image" in model

    def _install_hooks_sync(self, page) -> None:
        self.install_calls += 1

    def _goto_aistudio_sync(self, page) -> None:
        self.goto_calls += 1
        page.url = AI_STUDIO_URL
        page.has_default_makersuite = True
        page.has_textarea = True


def test_capture_template_prepares_image_model_before_botguard_snapshot_ready():
    page = FakePage(url=AI_STUDIO_URL, has_default_makersuite=True, has_textarea=True)
    session = TemplateCaptureImageSessionForTest(page)

    captured = session._capture_template_sync("gemini-3-pro-image-preview")

    assert captured["url"].endswith("GenerateContent")
    assert session.ensure_hook_calls == 1
    assert session.botguard_calls == 1
    assert session.prepare_calls == [(page, "gemini-3-pro-image-preview", 0)]
    assert session.install_calls == 2
    assert session.goto_calls == 1


def test_capture_template_uses_request_route_and_aborts_dummy_generation():
    page = FakePage(url=AI_STUDIO_URL, has_default_makersuite=True, has_textarea=True)
    session = TemplateCaptureSessionForTest(page)

    captured = session._capture_template_sync("gemini-3-flash-preview")

    assert captured == {
        "url": "https://aistudio.google.com/_/BardChatUi/data/batchexecute/GenerateContent",
        "headers": page.generate_content_headers,
        "body": page.generate_content_body,
    }
    assert page.filled_texts == ["template"]
    assert len(page.routed_requests) == 1
    assert page.routed_requests[0].aborted is True
    assert page.routed_requests[0].continued is False
    assert page.unroute_calls == ["**/*GenerateContent*"]
    assert session.wait_until_idle_calls == 1


def test_capture_template_recovers_when_page_redirects_to_docs_during_fill():
    page = FakePage(
        url=AI_STUDIO_URL,
        has_default_makersuite=True,
        has_textarea=True,
        redirect_on_next_fill=True,
    )
    session = TemplateCaptureSessionForTest(page)

    captured = session._capture_template_sync("gemini-3-flash-preview")

    assert captured["url"].endswith("GenerateContent")
    assert page.filled_texts == ["template"]
    assert session.goto_calls == 1
    assert session.install_calls == 1
    assert page.unroute_calls == ["**/*GenerateContent*", "**/*GenerateContent*"]
