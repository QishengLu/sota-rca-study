# Adding a New LLM Model

Goal: add a 13th base model to the catalog. **One YAML entry, no code changes.**

## Step 1. Edit `configs/models/catalog.yaml`

Append:

```yaml
models:
  # ... existing entries ...
  - alias: mynew-model
    name: actual-model-name-as-api-expects
    api_format: openai            # openai | anthropic | google
    base_url: https://api.myprovider.com/v1
    api_key_env: MYPROVIDER_API_KEY
    pricing: { input: 1.5, output: 5.0 }     # optional, USD per M tokens
    notes: My favorite new model
```

## Step 2. Add the API key to `.env`

```
MYPROVIDER_API_KEY=sk-xxx
```

## Step 3. Use it

In a matrix yaml:
```yaml
models:
  - alias: mynew-model
```

Or on the CLI:
```bash
uv run sota-rca matrix --frameworks thinkdepthai --models mynew-model --subset demo
```

That's it. The orchestrator reads `catalog.yaml`, looks up `mynew-model`, builds the env:

```
UTU_LLM_TYPE=chat.completions
UTU_LLM_MODEL=actual-model-name-as-api-expects
UTU_LLM_BASE_URL=https://api.myprovider.com/v1
UTU_LLM_API_KEY=$MYPROVIDER_API_KEY
# + compatibility shims OPENAI_* / ANTHROPIC_* / GOOGLE_* depending on api_format
```

and starts the subprocess. Every agent reads these vars, no special handling needed.

## Supported `api_format` values

| Value | LangChain wrapper | SDK |
|---|---|---|
| `openai` | `langchain_openai.ChatOpenAI` | `openai` |
| `anthropic` | `langchain_anthropic.ChatAnthropic` | `anthropic` |
| `google` | `langchain_google_genai.ChatGoogleGenerativeAI` | `google-generativeai` |

If your provider isn't OpenAI-compatible and needs a custom format, you'd extend `sdk/sota_rca/model_env.py` and the LLM factory inside each agent. But the vast majority of providers use the OpenAI-compatible API.

## UsageTracker support

The `UsageTracker` in `sdk/sota_rca/tracker.py` auto-hooks based on `api_format`:
- `openai` → patches `openai.resources.chat.completions.Completions.create` + `litellm.completion`
- `anthropic` → patches `anthropic.resources.messages.Messages.create`
- `google` → patches `google.generativeai.GenerativeModel.generate_content`

If your new provider uses the OpenAI SDK shape, `actual` token tracking works automatically. Otherwise it falls back to `estimated` (character-based ~3 chars/token).
