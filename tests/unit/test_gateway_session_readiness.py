import pytest

from aistudio_api.infrastructure.account import tier_detector
from aistudio_api.infrastructure.account.tier_detector import AccountTier, TierResult
from aistudio_api.infrastructure.gateway.session import AI_STUDIO_URL, BrowserSession


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
        self.goto_urls: list[str] = []
        self.wait_calls: list[int] = []

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
            return object()
        return None

    def title(self):
        return self.title_text


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


def test_goto_failure_reports_readiness_diagnostics():
    page = FakePage(title="Account page", body="Login completed but chat shell is missing")
    session = BrowserSession(port=0)

    with pytest.raises(RuntimeError) as exc_info:
        session._goto_aistudio_sync(page)

    message = str(exc_info.value)
    assert "AI Studio chat runtime not ready" in message
    assert "url=https://aistudio.google.com/app/prompts/new_chat" in message
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
