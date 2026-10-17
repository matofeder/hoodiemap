# AI providers: voice input and listing drafts

Both features are off until configured in `config.yaml` (`ai:`). HoodieMap speaks the OpenAI-compatible HTTP API to both, so any provider or local server that offers it works. Check your provider's docs for the exact base URL and model names; the values below are examples.

## Listing draft (LLM)

```yaml
ai:
  llm:
    base_url: https://api.deepseek.com/v1      # or e.g. https://dashscope-intl.aliyuncs.com/compatible-mode/v1 (Qwen)
    model: deepseek-chat                       # or e.g. qwen-plus
```

The API key goes into the environment, never into `config.yaml`:

```bash
export HOODIEMAP_LLM_API_KEY=sk-...
```

HoodieMap calls `POST {base_url}/chat/completions` with `response_format: {"type": "json_object"}` and retries without it if the server rejects the field. Reasoning output in `<think>…</think>` is ignored.

**What the model receives:** the address label, the listing fields filled so far, the neighbourhood POIs with distances, and the agent's transcript. **Never** the agent's or buyers' names, phones or e-mails, the photos, or coordinates. The transcript is sent as spoken, so the editor asks agents not to name the owner. Before using a provider outside the EU in production, check the GDPR side (transfers to third countries) with whoever handles data protection.

## Voice → text (local whisper)

```yaml
ai:
  stt:
    base_url: http://localhost:8001/v1   # your whisper server
    model: your-slovak-whisper-model     # whatever name the server expects; "" to omit
    language: sk
```

HoodieMap calls `POST {base_url}/audio/transcriptions` (multipart: `file`, `model`, `language`, `response_format=json`) and reads `text` from the answer. Servers that offer this endpoint include speaches (formerly faster-whisper-server) and whisper.cpp's server (set its inference path to `/v1/audio/transcriptions`, and let it convert non-WAV input with ffmpeg). Browsers record WebM/Opus (Safari: MP4/AAC), so the server must accept those formats. An optional key can be set in `$HOODIEMAP_STT_API_KEY`.

## Checking it

`GET /api/features` returns `{"ai": {"voice": true|false, "text": true|false}}`. The editor shows "Nahovoriť inzerát" after the presentation is created; recording needs HTTPS or `localhost` (on a phone over plain HTTP, upload a voice memo file instead).
