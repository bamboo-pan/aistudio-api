from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.gateway.session import BrowserSession, DIALOG_CLEANUP_JS


def main() -> None:
    store = AccountStore()
    auth = store.get_active_auth_path()
    print("AUTH_EXISTS", bool(auth))
    session = BrowserSession(port=19423)
    session._auth_file = auth
    observed: list[str] = []
    try:
        page = session._ensure_hook_page_sync()
        page.evaluate(DIALOG_CLEANUP_JS)
        textarea = page.query_selector("textarea")
        if textarea is None:
            print("NO_TEXTAREA")
            return
        session._fill_prompt_text_sync(page, textarea, "probe send route")
        page.wait_for_timeout(1200)

        def on_route(route):
            request = route.request
            body = request.post_data or ""
            if "aistudio.google.com" in request.url or body:
                observed.append(f"url={request.url} body_len={len(body)} body_head={body[:120]!r}")
            route.continue_()

        page.route("**/*", on_route)
        try:
            clicked = session._click_run_button_sync(page)
            print("CLICKED", clicked)
            for _ in range(80):
                if observed:
                    break
                page.wait_for_timeout(250)
        finally:
            page.unroute("**/*", on_route)
        print("OBSERVED_COUNT", len(observed))
        for item in observed[:20]:
            print(item)
        print("DIAGNOSTICS", session._format_chat_runtime_diagnostics_sync(page))
    finally:
        session._close_sync()


if __name__ == "__main__":
    main()