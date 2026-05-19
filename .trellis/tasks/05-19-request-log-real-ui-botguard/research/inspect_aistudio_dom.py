import json

from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.gateway.session import BrowserSession, DIALOG_CLEANUP_JS


INSPECT_JS = r"""
() => {
  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const text = (el) => [
    el.innerText,
    el.textContent,
    el.getAttribute('aria-label'),
    el.getAttribute('title'),
    el.getAttribute('data-tooltip'),
    el.getAttribute('data-test-id'),
    el.querySelector('mat-icon')?.textContent,
    el.querySelector('[data-mat-icon-name]')?.getAttribute('data-mat-icon-name'),
  ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  const rectOf = (el) => {
    const rect = el.getBoundingClientRect();
    return [rect.x, rect.y, rect.width, rect.height];
  };
  return {
    location: location.href,
    textareas: Array.from(document.querySelectorAll('textarea')).map((el) => ({
      visible: visible(el),
      aria: el.getAttribute('aria-label'),
      placeholder: el.getAttribute('placeholder'),
      value: el.value,
      rect: rectOf(el),
    })),
    contenteditable: Array.from(document.querySelectorAll('[contenteditable="true"]')).map((el) => ({
      visible: visible(el),
      label: text(el).slice(0, 180),
      role: el.getAttribute('role'),
      aria: el.getAttribute('aria-label'),
      rect: rectOf(el),
    })),
    inputs: Array.from(document.querySelectorAll('input')).filter(visible).map((el) => ({
      type: el.type,
      aria: el.getAttribute('aria-label'),
      placeholder: el.getAttribute('placeholder'),
      value: el.value,
      rect: rectOf(el),
    })),
    buttons: Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible).map((el) => ({
      label: text(el).slice(0, 180),
      disabled: !!el.disabled,
      ariaDisabled: el.getAttribute('aria-disabled'),
      classes: String(el.className || '').slice(0, 160),
      rect: rectOf(el),
    })).slice(-80),
    bodyTail: (document.body?.innerText || '').slice(-1500),
  };
}
"""


def main() -> None:
    store = AccountStore()
    auth = store.get_active_auth_path()
    print("AUTH_EXISTS", bool(auth))
    session = BrowserSession(port=19422)
    session._auth_file = auth
    try:
        page = session._ensure_hook_page_sync()
        print("URL", page.url)
        print("TITLE", page.title())
        page.evaluate(DIALOG_CLEANUP_JS)
        print("READY", session._format_chat_runtime_diagnostics_sync(page))
        print("BEFORE_FILL")
        print(json.dumps(page.evaluate(INSPECT_JS), ensure_ascii=False, indent=2))
        textarea = page.query_selector("textarea")
        if textarea is not None:
          session._fill_prompt_text_sync(page, textarea, "diagnostic prompt")
          page.wait_for_timeout(1200)
          print("AFTER_FILL")
          print(json.dumps(page.evaluate(INSPECT_JS), ensure_ascii=False, indent=2))
    finally:
        session._close_sync()


if __name__ == "__main__":
  main()