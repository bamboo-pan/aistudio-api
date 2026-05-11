from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


SRC = Path('/mnt/c/Users/bamboo/Desktop/aistudio-api')
ACCOUNTS_DIR = '/home/bamboo/aistudio-api/data/accounts'
EXCLUDED_DIRS = {'.git', '.venv', 'data', '__pycache__', '.pytest_cache'}


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.stdout:
        print(result.stdout, end='')
    result.check_returncode()
    return result


def copy_repo(src: Path, dst: Path) -> None:
    ignore = shutil.ignore_patterns('.git', '.venv', 'data', '__pycache__', '.pytest_cache', '*.pyc')
    for item in src.iterdir():
        if item.name in EXCLUDED_DIRS:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=ignore)
        else:
            shutil.copy2(item, target)


def smoke_code() -> str:
    return r'''
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from aistudio_api.domain.model_capabilities import list_model_metadata
from aistudio_api.infrastructure.account.account_store import AccountStore


def contains_all(text, needles):
    return all(needle in text for needle in needles)


root = Path.cwd()
index_html = (root / "src" / "aistudio_api" / "static" / "index.html").read_text(encoding="utf-8")
app_js = (root / "src" / "aistudio_api" / "static" / "app.js").read_text(encoding="utf-8")
style_css = (root / "src" / "aistudio_api" / "static" / "style.css").read_text(encoding="utf-8")

accounts_dir = Path(os.environ["AISTUDIO_ACCOUNTS_DIR"])
real_store = AccountStore(accounts_dir=accounts_dir)
real_accounts = real_store.list_accounts()
real_with_auth = sum(1 for account in real_accounts if real_store.get_auth_path(account.id) is not None)

models = list_model_metadata()
image_models = [model for model in models if model.get("capabilities", {}).get("image_output")]
image_generation_metadata = image_models[0].get("image_generation", {}) if image_models else {}

print("p1_item9_real_accounts_dir_exists", accounts_dir.is_dir())
print("p1_item9_real_accounts_count", len(real_accounts))
print("p1_item9_real_accounts_with_auth", real_with_auth)
print("p1_item9_models_have_image_output", bool(image_models))
print("p1_item9_models_have_sizes", bool(image_generation_metadata.get("sizes")))
print("p1_item9_models_have_url_format", "url" in image_generation_metadata.get("response_formats", []))
print(
    "p1_item9_chat_upload_controls",
    contains_all(index_html, ["attachChatImages($event)", "$refs.chatFileInput.click()", "chat-attachments", "msg-images"]),
)
print(
    "p1_item9_chat_payload_support",
    contains_all(app_js, ["chatCanSend", "selectedCaps.image_input", "image_url:{url:img.url}", "fileToDataUrl"]),
)
print(
    "p1_item9_image_page_controls",
    contains_all(index_html, ["selectImageModel(m.id)", "imageSize", "imageCount", "generateImage()"]),
)
print(
    "p1_item9_image_generation_payload",
    contains_all(app_js, ["/v1/images/generations", "response_format:'url'", "normalizeImageCount", "imageLastRequest"]),
)
print(
    "p1_item9_gallery_download_retry",
    contains_all(index_html, ["downloadImage(item)", "retryImage(item)", "retryLastImage()", "image-gallery"]),
)
print(
    "p1_item9_local_history",
    contains_all(app_js, ["localStorage.getItem('aistudio.imageHistory')", "saveImageHistory", "clearImageHistory"]),
)
print(
    "p1_item9_static_styles",
    contains_all(style_css, [".chat-attachment", ".image-workspace", ".image-gallery", ".image-card"]),
)

port = "18091"
server_env = os.environ.copy()
server_env["AISTUDIO_USE_PURE_HTTP"] = "1"
server_env["AISTUDIO_PORT"] = port
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "aistudio_api.api.app:app", "--host", "127.0.0.1", "--port", port, "--log-level", "warning"],
    cwd=root,
    env=server_env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)


def fetch(path):
    with urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
        return response.read().decode("utf-8")


try:
    deadline = time.time() + 30
    loaded = False
    while time.time() < deadline:
        if server.poll() is not None:
            break
        try:
            fetch("/static/index.html")
            loaded = True
            break
        except Exception:
            time.sleep(0.25)
    server_index = fetch("/static/index.html") if loaded else ""
    server_app = fetch("/static/app.js") if loaded else ""
    server_models = json.loads(fetch("/v1/models")) if loaded else {"data": []}
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)

server_image_models = [model for model in server_models.get("data", []) if model.get("capabilities", {}).get("image_output")]
print("p1_item9_server_static_index_loaded", "image-page" in server_index and "chatFileInput" in server_index)
print("p1_item9_server_static_app_loaded", "/v1/images/generations" in server_app and "aistudio.imageHistory" in server_app)
print("p1_item9_server_models_include_image_generation", bool(server_image_models and server_image_models[0].get("image_generation", {}).get("sizes")))
print("p1_item9_secrets_printed", False)
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='aistudio-api-verify-p1-item9-copilot-', dir='/home/bamboo'))
    print(f'temp_dir {tmp}')
    copy_repo(SRC, tmp)

    venv_python = tmp / '.venv' / 'bin' / 'python'
    run(['python3', '-m', 'venv', '.venv'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '--upgrade', 'pip'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '-e', '.[test]'], cwd=tmp)

    env = os.environ.copy()
    env['AISTUDIO_ACCOUNTS_DIR'] = ACCOUNTS_DIR
    run([str(venv_python), '-m', 'pytest', '-q'], cwd=tmp, env=env)
    run([str(venv_python), '-m', 'compileall', '-q', 'src', 'tests'], cwd=tmp, env=env)
    if shutil.which('node'):
        run(['node', '--check', 'src/aistudio_api/static/app.js'], cwd=tmp, env=env)
        print('node_check passed')
    else:
        print('node_check node_unavailable')
    run([str(venv_python), '-c', smoke_code()], cwd=tmp, env=env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())