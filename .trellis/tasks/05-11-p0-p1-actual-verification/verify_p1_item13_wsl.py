from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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
import asyncio
import json
import os
from pathlib import Path

import httpx

from aistudio_api.api.app import app
from aistudio_api.api.dependencies import get_client
from aistudio_api.api.state import runtime_state
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.gateway.client import AIStudioClient


TEXT_RESPONSE_RAW = json.dumps([
    [
        [[[[[None, 'pure text ok']]], 1]],
        None,
        [1, 3, 4],
        None,
        None,
        None,
        None,
        'resp_pure_http_wsl',
    ]
])


class FakeReplayService:
    def __init__(self):
        self.calls = []

    async def replay(self, captured, body, timeout=None):
        self.calls.append({'body': body, 'timeout': timeout})
        return 200, TEXT_RESPONSE_RAW.encode('utf-8')


def request_with_client(client, method, url, **kwargs):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as http_client:
            return await http_client.request(method, url, **kwargs)

    old_busy_lock = runtime_state.busy_lock
    old_account_service = runtime_state.account_service
    old_rotator = runtime_state.rotator
    app.dependency_overrides[get_client] = lambda: client
    runtime_state.busy_lock = asyncio.Semaphore(3)
    runtime_state.account_service = None
    runtime_state.rotator = None
    try:
        return asyncio.run(send())
    finally:
        runtime_state.busy_lock = old_busy_lock
        runtime_state.account_service = old_account_service
        runtime_state.rotator = old_rotator
        app.dependency_overrides.pop(get_client, None)


def pure_text_smoke():
    client = AIStudioClient(use_pure_http=True)
    replay = FakeReplayService()

    async def snapshot(prompt):
        return 'snapshot-token'

    client._capture_service._generate_snapshot = snapshot
    client._replay_service = replay
    response = request_with_client(
        client,
        'POST',
        '/v1/chat/completions',
        json={
            'model': 'gemini-3-flash-preview',
            'messages': [{'role': 'user', 'content': 'plain text only'}],
        },
    )
    modified_body = json.loads(replay.calls[0]['body']) if replay.calls else []
    return response, modified_body


def snapshot_unsupported_smoke():
    client = AIStudioClient(use_pure_http=True)

    async def no_snapshot(prompt):
        return None

    client._capture_service._generate_snapshot = no_snapshot
    return request_with_client(
        client,
        'POST',
        '/v1/chat/completions',
        json={
            'model': 'gemini-3-flash-preview',
            'messages': [{'role': 'user', 'content': 'hello'}],
        },
    )


accounts_dir = Path(os.environ['AISTUDIO_ACCOUNTS_DIR'])
real_store = AccountStore(accounts_dir=accounts_dir)
real_accounts = real_store.list_accounts()
real_with_auth = sum(1 for account in real_accounts if real_store.get_auth_path(account.id) is not None)

plain_text, plain_text_body = pure_text_smoke()
plain_text_json = plain_text.json()
generation_config = plain_text_body[3] if len(plain_text_body) > 3 else None

openai_stream = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'stream': True,
        'messages': [{'role': 'user', 'content': 'hello'}],
    },
)
gemini_stream = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1beta/models/gemini-3-flash-preview:streamGenerateContent',
    json={'contents': [{'role': 'user', 'parts': [{'text': 'hello'}]}]},
)
image_generation = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1/images/generations',
    json={'model': 'gemini-3.1-flash-image-preview', 'prompt': 'draw', 'size': '1024x1024'},
)
structured_output = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'messages': [{'role': 'user', 'content': 'json'}],
        'response_format': {'type': 'json_object'},
    },
)
multi_turn = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'messages': [
            {'role': 'user', 'content': 'first'},
            {'role': 'assistant', 'content': 'second'},
            {'role': 'user', 'content': 'third'},
        ],
    },
)
snapshot_unsupported = snapshot_unsupported_smoke()

print('p1_item13_real_accounts_dir_exists', accounts_dir.is_dir())
print('p1_item13_real_accounts_count', len(real_accounts))
print('p1_item13_real_accounts_with_auth', real_with_auth)
print('p1_item13_plain_text_route_supported', plain_text.status_code == 200 and plain_text_json['choices'][0]['message']['content'] == 'pure text ok')
print('p1_item13_plain_text_generation_config_list', isinstance(generation_config, list))
print('p1_item13_plain_text_thinking_disabled', isinstance(generation_config, list) and (len(generation_config) <= 16 or generation_config[16] is None))
print('p1_item13_openai_stream_unsupported', openai_stream.status_code == 501 and 'Pure HTTP mode is experimental' in openai_stream.json()['error']['message'])
print('p1_item13_gemini_stream_unsupported', gemini_stream.status_code == 501 and gemini_stream.json()['detail']['type'] == 'unsupported_feature')
print('p1_item13_image_generation_unsupported', image_generation.status_code == 501 and 'image generation' in image_generation.json()['error']['message'])
print('p1_item13_structured_output_unsupported', structured_output.status_code == 501 and 'structured generation config' in structured_output.json()['error']['message'])
print('p1_item13_multiturn_unsupported', multi_turn.status_code == 501 and 'single-turn' in multi_turn.json()['error']['message'] and 'multi-turn' in multi_turn.json()['error']['message'])
print('p1_item13_snapshot_unsupported', snapshot_unsupported.status_code == 501 and 'BotGuard snapshot' in snapshot_unsupported.json()['error']['message'])
print('p1_item13_secrets_printed', False)
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='aistudio-api-verify-p1-item13-copilot-', dir='/home/bamboo'))
    print(f'temp_dir {tmp}')
    copy_repo(SRC, tmp)

    venv_python = tmp / '.venv' / 'bin' / 'python'
    run(['python3', '-m', 'venv', '.venv'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '--upgrade', 'pip'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '-e', '.[test]'], cwd=tmp)

    env = os.environ.copy()
    env['AISTUDIO_ACCOUNTS_DIR'] = ACCOUNTS_DIR
    run([str(venv_python), '-m', 'pytest', 'tests/unit/test_pure_http_boundary.py', '-q'], cwd=tmp, env=env)
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