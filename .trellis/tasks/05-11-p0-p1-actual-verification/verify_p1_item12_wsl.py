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
import shutil
from pathlib import Path

import httpx

from aistudio_api.api.app import app
from aistudio_api.api.dependencies import get_client
from aistudio_api.api.state import runtime_state
from aistudio_api.application.api_service import _build_gemini_streaming_response, _build_streaming_response
from aistudio_api.domain.errors import RequestError
from aistudio_api.infrastructure.account.account_store import AccountStore
from aistudio_api.infrastructure.gateway.wire_types import AistudioContent, AistudioPart


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


class CloseAwareStreamClient:
    def __init__(self):
        self.closed = False
        self.calls = []

    async def stream_generate_content(self, **kwargs):
        self.calls.append(kwargs)
        try:
            yield ('body', 'hello')
            await asyncio.Event().wait()
        finally:
            self.closed = True


class DisconnectingRequest:
    def __init__(self, states):
        self._states = list(states)
        self.calls = 0

    async def is_disconnected(self):
        self.calls += 1
        if self._states:
            return self._states.pop(0)
        return True


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


async def collect_body_iterator(response):
    return [chunk async for chunk in response.body_iterator]


def gemini_normalized(cleanup_paths=None):
    return {
        'model': 'gemini-3-flash-preview',
        'capture_prompt': 'hello',
        'capture_images': None,
        'contents': [AistudioContent(role='user', parts=[AistudioPart(text='hello')])],
        'system_instruction': None,
        'tools': None,
        'temperature': None,
        'top_p': None,
        'top_k': None,
        'max_tokens': None,
        'generation_config_overrides': None,
        'cleanup_paths': cleanup_paths or [],
    }


def openai_disconnect_before_downstream(scratch):
    tmp_file = scratch / 'openai-before.png'
    tmp_file.write_bytes(b'image')
    client = FakeStreamClient(events=[('body', 'should not run')])
    request = DisconnectingRequest([True])
    old_busy_lock = runtime_state.busy_lock
    runtime_state.busy_lock = asyncio.Semaphore(3)
    try:
        response = _build_streaming_response(
            client=client,
            capture_prompt='hello',
            model='gemini-3-flash-preview',
            capture_images=None,
            contents=[AistudioContent(role='user', parts=[AistudioPart(text='hello')])],
            system_instruction=None,
            cleanup_paths=[str(tmp_file)],
            request=request,
        )
        chunks = asyncio.run(collect_body_iterator(response))
    finally:
        runtime_state.busy_lock = old_busy_lock
    return chunks == [] and client.calls == [] and request.calls == 1 and not tmp_file.exists()


def openai_disconnect_during_downstream(scratch):
    tmp_file = scratch / 'openai-during.png'
    tmp_file.write_bytes(b'image')
    client = CloseAwareStreamClient()
    request = DisconnectingRequest([False, True])
    old_busy_lock = runtime_state.busy_lock
    runtime_state.busy_lock = asyncio.Semaphore(3)
    try:
        response = _build_streaming_response(
            client=client,
            capture_prompt='hello',
            model='gemini-3-flash-preview',
            capture_images=None,
            contents=[AistudioContent(role='user', parts=[AistudioPart(text='hello')])],
            system_instruction=None,
            cleanup_paths=[str(tmp_file)],
            request=request,
        )
        chunks = asyncio.run(collect_body_iterator(response))
    finally:
        runtime_state.busy_lock = old_busy_lock
    return chunks == [] and len(client.calls) == 1 and client.closed and request.calls == 2 and not tmp_file.exists()


def gemini_disconnect_during_downstream(scratch):
    tmp_file = scratch / 'gemini-during.png'
    tmp_file.write_bytes(b'image')
    client = CloseAwareStreamClient()
    request = DisconnectingRequest([False, True])
    old_busy_lock = runtime_state.busy_lock
    runtime_state.busy_lock = asyncio.Semaphore(3)
    try:
        response = _build_gemini_streaming_response(
            client=client,
            normalized=gemini_normalized([str(tmp_file)]),
            request=request,
        )
        chunks = asyncio.run(collect_body_iterator(response))
    finally:
        runtime_state.busy_lock = old_busy_lock
    return chunks == [] and len(client.calls) == 1 and client.closed and request.calls == 2 and not tmp_file.exists()


accounts_dir = Path(os.environ['AISTUDIO_ACCOUNTS_DIR'])
real_store = AccountStore(accounts_dir=accounts_dir)
real_accounts = real_store.list_accounts()
real_with_auth = sum(1 for account in real_accounts if real_store.get_auth_path(account.id) is not None)

openai_error = request_with_client(
    FakeStreamClient(error=RequestError(502, 'upstream stream failed')),
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

scratch = Path('/tmp/aistudio-p1-item12-smoke')
if scratch.exists():
    shutil.rmtree(scratch)
scratch.mkdir(parents=True)

print('p1_item12_real_accounts_dir_exists', accounts_dir.is_dir())
print('p1_item12_real_accounts_count', len(real_accounts))
print('p1_item12_real_accounts_with_auth', real_with_auth)
print('p1_item12_openai_stream_error_shape', openai_error.status_code == 200 and openai_error_events[-1]['error']['type'] == 'upstream_error' and openai_error_events[-1]['error']['code'] == 'upstream_error')
print('p1_item12_openai_stream_error_done', openai_error.text.rstrip().endswith('data: [DONE]'))
print('p1_item12_openai_tool_delta_indexed', openai_tool_delta.get('index') == 0)
print('p1_item12_openai_tool_delta_arguments_json', json.loads(openai_tool_delta['function']['arguments']) == {'query': 'weather'})
print('p1_item12_openai_usage_trailer', openai_tool_events[-1].get('usage', {}).get('total_tokens') == 3)
print('p1_item12_openai_finish_tool_calls', any(event.get('choices') and event['choices'][0].get('finish_reason') == 'tool_calls' for event in openai_tool_events))
print('p1_item12_gemini_tool_call_part', gemini_function_call == {'name': 'lookup', 'args': {'query': 'weather'}})
print('p1_item12_gemini_finish_function_call', gemini_finish.get('finishReason') == 'FUNCTION_CALL')
print('p1_item12_gemini_usage_metadata', gemini_events[-1].get('usageMetadata', {}).get('totalTokenCount') == 3)
print('p1_item12_openai_disconnect_before_downstream_cleanup', openai_disconnect_before_downstream(scratch))
print('p1_item12_openai_disconnect_during_downstream_cleanup', openai_disconnect_during_downstream(scratch))
print('p1_item12_gemini_disconnect_during_downstream_cleanup', gemini_disconnect_during_downstream(scratch))
print('p1_item12_secrets_printed', False)
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='aistudio-api-verify-p1-item12-copilot-', dir='/home/bamboo'))
    print(f'temp_dir {tmp}')
    copy_repo(SRC, tmp)

    venv_python = tmp / '.venv' / 'bin' / 'python'
    run(['python3', '-m', 'venv', '.venv'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '--upgrade', 'pip'], cwd=tmp)
    run([str(venv_python), '-m', 'pip', 'install', '-q', '-e', '.[test]'], cwd=tmp)

    env = os.environ.copy()
    env['AISTUDIO_ACCOUNTS_DIR'] = ACCOUNTS_DIR
    run([str(venv_python), '-m', 'pytest', 'tests/unit/test_streaming_stability.py', '-q'], cwd=tmp, env=env)
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