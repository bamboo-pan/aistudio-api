# OpenCode Temporary Config Research

## Findings

* OpenCode supports project config files named `opencode.json` or `opencode.jsonc`.
* Config precedence includes global config, `OPENCODE_CONFIG`, project config, and `OPENCODE_CONFIG_CONTENT`; sources are merged.
* `OPENCODE_CONFIG` points OpenCode at a custom config file path.
* `OPENCODE_CONFIG_CONTENT` can provide inline runtime overrides.
* `OPENCODE_CONFIG_DIR` points at a custom `.opencode`-style directory for agents/commands/plugins.
* Custom OpenAI-compatible providers use `npm: "@ai-sdk/openai-compatible"`, `options.baseURL`, optional `options.apiKey`, and a `models` map.
* If the provider/model uses OpenAI Responses, OpenCode docs recommend `@ai-sdk/openai`; for this task's OpenCode path, README recommends the OpenAI-compatible Chat Completions provider.

## Safety Plan

* Do not run `opencode providers login`, `providers logout`, or `/connect`.
* Do not edit `C:\Users\bamboo\.config\opencode` or other global OpenCode paths.
* Run `opencode run` from a temporary Windows directory with an `opencode.json` file dedicated to this validation.
* Set `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, and `XDG_CACHE_HOME` to temporary directories when invoking OpenCode, so generated auth/state/log/cache files are isolated from the user's global OpenCode directories.
* Set `OPENCODE_CONFIG` to the temporary config file and `OPENCODE_CONFIG_DIR` to an empty temporary config directory.

## Candidate Provider Config

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "aistudio/gemini-3-flash-preview",
  "small_model": "aistudio/gemini-3-flash-preview",
  "share": "disabled",
  "autoupdate": false,
  "provider": {
    "aistudio": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "AI Studio API local",
      "options": {
        "baseURL": "http://127.0.0.1:18080/v1",
        "apiKey": "unused"
      },
      "models": {
        "gemini-3-flash-preview": {
          "name": "Gemini 3 Flash Preview",
          "limit": {
            "context": 1048576,
            "output": 65536
          }
        }
      }
    }
  }
}
```
