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
from aistudio_api.domain.errors import RequestError
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.gateway.client import AIStudioClient


class FakeStreamClient:
    def __init__(self, events=None, *, error=None):
        self.events = list(events or [])
        self.error = error
        self.calls = []

    async def stream_generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        for event in self.events:
            yield event


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


def events(response):
    return [
        json.loads(line.removeprefix('data: '))
        for line in response.text.splitlines()
        if line.startswith('data: ') and line != 'data: [DONE]'
    ]


accounts_dir = Path(os.environ['AISTUDIO_ACCOUNTS_DIR'])
real_store = AccountStore(accounts_dir=accounts_dir)
real_accounts = real_store.list_accounts()
real_with_auth = sum(1 for account in real_accounts if real_store.get_auth_path(account.id) is not None)

openai_error = request_with_client(
    FakeStreamClient(error=RequestError(501, 'Pure HTTP mode is experimental and does not support streaming')),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'stream': True,
        'messages': [{'role': 'user', 'content': 'hello'}],
    },
)
openai_error_events = events(openai_error)

openai_tool = request_with_client(
    FakeStreamClient(events=[
        ('tool_calls', [{'name': 'lookup', 'arguments': {'query': 'weather'}}]),
        ('usage', {'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3}),
    ]),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'stream': True,
        'messages': [{'role': 'user', 'content': 'call a tool'}],
        'tools': [{'type': 'function', 'function': {'name': 'lookup', 'parameters': {'type': 'object'}}}],
    },
)
openai_tool_events = events(openai_tool)
openai_tool_delta = next(event for event in openai_tool_events if event.get('choices') and event['choices'][0]['delta'].get('tool_calls'))['choices'][0]['delta']['tool_calls'][0]

gemini_tool = request_with_client(
    FakeStreamClient(events=[
        ('tool_calls', [{'name': 'lookup', 'args': {'query': 'weather'}}]),
        ('usage', {'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3}),
    ]),
    'POST',
    '/v1beta/models/gemini-3-flash-preview:streamGenerateContent',
    json={'contents': [{'role': 'user', 'parts': [{'text': 'call a tool'}]}]},
)
gemini_events = events(gemini_tool)
gemini_function_call = gemini_events[0]['candidates'][0]['content']['parts'][0]['functionCall']
gemini_finish = gemini_events[-1]['candidates'][0]

pure_stream = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'stream': True,
        'messages': [{'role': 'user', 'content': 'hello'}],
    },
)
pure_image = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1/images/generations',
    json={'model': 'gemini-3.1-flash-image-preview', 'prompt': 'draw', 'size': '1024x1024'},
)
pure_snapshot = request_with_client(
    AIStudioClient(use_pure_http=True),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'messages': [{'role': 'user', 'content': 'hello'}],
    },
)

print('p1_items12_13_real_accounts_dir_exists', accounts_dir.is_dir())
print('p1_items12_13_real_accounts_count', len(real_accounts))
print('p1_items12_13_real_accounts_with_auth', real_with_auth)
print('p1_item12_openai_stream_error_shape', openai_error.status_code == 200 and openai_error_events[-1]['error']['type'] == 'unsupported_feature' and openai_error_events[-1]['error']['code'] == 'unsupported_feature')
print('p1_item12_openai_stream_error_done', openai_error.text.rstrip().endswith('data: [DONE]'))
print('p1_item12_openai_tool_delta_indexed', openai_tool_delta.get('index') == 0)
print('p1_item12_openai_tool_delta_arguments_json', json.loads(openai_tool_delta['function']['arguments']) == {'query': 'weather'})
print('p1_item12_openai_usage_trailer', openai_tool_events[-1].get('usage', {}).get('total_tokens') == 3)
print('p1_item12_openai_finish_tool_calls', any(event.get('choices') and event['choices'][0].get('finish_reason') == 'tool_calls' for event in openai_tool_events))
print('p1_item12_gemini_tool_call_part', gemini_function_call == {'name': 'lookup', 'args': {'query': 'weather'}})
print('p1_item12_gemini_finish_function_call', gemini_finish.get('finishReason') == 'FUNCTION_CALL')
print('p1_item12_gemini_usage_metadata', gemini_events[-1].get('usageMetadata', {}).get('totalTokenCount') == 3)
print('p1_item13_pure_http_stream_unsupported', pure_stream.status_code == 501 and 'Pure HTTP mode is experimental' in pure_stream.json()['error']['message'])
print('p1_item13_pure_http_image_unsupported', pure_image.status_code == 501 and 'image generation' in pure_image.json()['error']['message'])
print('p1_item13_pure_http_snapshot_unsupported', pure_snapshot.status_code == 501 and 'BotGuard snapshot' in pure_snapshot.json()['error']['message'])
print('p1_items12_13_secrets_printed', False)
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='aistudio-api-verify-p1-items12-13-copilot-', dir='/home/bamboo'))
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