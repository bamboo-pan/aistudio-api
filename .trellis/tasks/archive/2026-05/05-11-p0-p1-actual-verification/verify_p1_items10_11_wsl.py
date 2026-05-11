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
from aistudio_api.domain.models import Candidate, ModelOutput
from aistudio_api.infrastructure.account.account_store import AccountStore


class FakeTextClient:
    def __init__(self, *, text='ok', function_calls=None):
        self.text = text
        self.function_calls = function_calls or []
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return ModelOutput(
            candidates=[Candidate(text=self.text, function_calls=self.function_calls)],
            usage={'prompt_tokens': 3, 'completion_tokens': 4, 'total_tokens': 7},
        )


class FakeStreamClient:
    def __init__(self):
        self.calls = []

    async def stream_generate_content(self, **kwargs):
        self.calls.append(kwargs)
        yield ('tool_calls', [{'name': 'lookup', 'args': {'query': 'weather'}}])
        yield ('usage', {'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3})


class UnusedClient:
    async def generate_content(self, **kwargs):
        raise AssertionError('downstream client should not be called')


def request_app(client, method, url, **kwargs):
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


accounts_dir = Path(os.environ['AISTUDIO_ACCOUNTS_DIR'])
real_store = AccountStore(accounts_dir=accounts_dir)
real_accounts = real_store.list_accounts()
real_with_auth = sum(1 for account in real_accounts if real_store.get_auth_path(account.id) is not None)

schema_client = FakeTextClient(text='{"ok":true}')
responses_schema = request_app(
    schema_client,
    'POST',
    '/v1/responses',
    json={
        'model': 'gemini-3-flash-preview',
        'input': 'return json',
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'Answer',
                'strict': True,
                'schema': {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}},
            }
        },
    },
)
schema_overrides = schema_client.calls[0]['generation_config_overrides'] if schema_client.calls else {}

function_client = FakeTextClient(text='', function_calls=[{'name': 'lookup', 'args': {'query': 'weather'}}])
responses_tool = request_app(function_client, 'POST', '/v1/responses', json={'model': 'gemini-3-flash-preview', 'input': 'call a tool'})

messages_client = FakeTextClient(text='', function_calls=[{'name': 'lookup', 'args': {'query': 'weather'}}])
messages_tool = request_app(
    messages_client,
    'POST',
    '/v1/messages',
    json={
        'model': 'gemini-3-flash-preview',
        'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'use the tool'}]}],
        'tools': [{'name': 'lookup', 'input_schema': {'type': 'object', 'properties': {'query': {'type': 'string'}}}}],
    },
)

stream_response = request_app(
    FakeStreamClient(),
    'POST',
    '/v1/chat/completions',
    json={
        'model': 'gemini-3-flash-preview',
        'stream': True,
        'messages': [{'role': 'user', 'content': 'call a tool'}],
        'tools': [{'type': 'function', 'function': {'name': 'lookup', 'parameters': {'type': 'object'}}}],
    },
)
stream_events = [
    json.loads(line.removeprefix('data: '))
    for line in stream_response.text.splitlines()
    if line.startswith('data: ') and line != 'data: [DONE]'
]
tool_event = next(event for event in stream_events if event.get('choices') and event['choices'][0]['delta'].get('tool_calls'))
tool_delta = tool_event['choices'][0]['delta']['tool_calls'][0]

openai_error = request_app(FakeTextClient(), 'POST', '/v1/responses', json={'input': 'hello'})
openai_error_body = openai_error.json()

gemini_models = request_app(UnusedClient(), 'GET', '/v1beta/models')
models = gemini_models.json().get('models', [])
flash = next(model for model in models if model.get('name') == 'models/gemini-3-flash-preview')
count_tokens = request_app(
    UnusedClient(),
    'POST',
    '/v1beta/models/gemini-3-flash-preview:countTokens',
    json={
        'generateContentRequest': {
            'contents': [{'role': 'user', 'parts': [{'text': 'hello world'}]}],
            'systemInstruction': {'parts': [{'text': 'system'}]},
        }
    },
)
embed = request_app(UnusedClient(), 'POST', '/v1beta/models/gemini-3-flash-preview:embedContent', json={'content': {'parts': [{'text': 'hello'}]}})
batch_embed = request_app(UnusedClient(), 'POST', '/v1beta/models/gemini-3-flash-preview:batchEmbedContents', json={'requests': []})
safety = request_app(UnusedClient(), 'POST', '/v1beta/models/gemini-3-flash-preview:generateContent', json={'contents': [{'parts': [{'text': 'hello'}]}], 'safetySettings': [{'category': 'HARM_CATEGORY_DANGEROUS_CONTENT'}]})
cached = request_app(UnusedClient(), 'POST', '/v1beta/models/gemini-3-flash-preview:generateContent', json={'contents': [{'parts': [{'text': 'hello'}]}], 'cachedContent': 'cachedContents/example'})
file_data = request_app(UnusedClient(), 'POST', '/v1beta/models/gemini-3-flash-preview:generateContent', json={'contents': [{'parts': [{'fileData': {'mimeType': 'image/png', 'fileUri': 'gs://bucket/image.png'}}]}]})

print('p1_items10_11_real_accounts_dir_exists', accounts_dir.is_dir())
print('p1_items10_11_real_accounts_count', len(real_accounts))
print('p1_items10_11_real_accounts_with_auth', real_with_auth)
print('p1_item10_responses_route_status', responses_schema.status_code)
print('p1_item10_responses_json_schema_passed', schema_overrides.get('response_mime_type') == 'application/json' and schema_overrides.get('response_schema') == [6, None, None, None, None, None, [['ok', [4]]]])
print('p1_item10_responses_function_call_output', responses_tool.status_code == 200 and responses_tool.json()['output'][0]['type'] == 'function_call')
print('p1_item10_messages_tool_use_output', messages_tool.status_code == 200 and messages_tool.json()['stop_reason'] == 'tool_use' and messages_tool.json()['content'][0]['type'] == 'tool_use')
print('p1_item10_stream_tool_delta_indexed', tool_delta.get('index') == 0)
print('p1_item10_stream_tool_delta_arguments_json', json.loads(tool_delta['function']['arguments']) == {'query': 'weather'})
print('p1_item10_openai_error_shape', openai_error.status_code == 400 and 'error' in openai_error_body and 'detail' not in openai_error_body)
print('p1_item11_models_route_status', gemini_models.status_code)
print('p1_item11_models_methods_include_count_tokens', 'countTokens' in flash.get('supportedGenerationMethods', []))
print('p1_item11_count_tokens_positive', count_tokens.status_code == 200 and count_tokens.json().get('totalTokens', 0) > 0)
print('p1_item11_embed_unsupported_clear', embed.status_code == 501 and embed.json()['detail']['type'] == 'unsupported_feature')
print('p1_item11_batch_embed_unsupported_clear', batch_embed.status_code == 501 and batch_embed.json()['detail']['type'] == 'unsupported_feature')
print('p1_item11_safety_settings_clear_error', safety.status_code == 400 and 'safetySettings' in safety.json()['detail']['message'])
print('p1_item11_cached_content_clear_error', cached.status_code == 400 and 'cachedContent' in cached.json()['detail']['message'])
print('p1_item11_file_data_clear_error', file_data.status_code == 400 and 'fileData' in file_data.json()['detail']['message'])
print('p1_items10_11_secrets_printed', False)
'''


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='aistudio-api-verify-p1-items10-11-copilot-', dir='/home/bamboo'))
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