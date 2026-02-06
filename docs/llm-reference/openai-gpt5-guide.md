# OpenAI GPT-5 Model Family Reference

> Source: https://platform.openai.com/docs/guides/gpt-5
> Saved: 2026-02-06

## Models

| Variant | Best for |
|---------|----------|
| gpt-5.2 | Complex reasoning, broad world knowledge, multi-step agentic tasks |
| gpt-5.2-pro | Tough problems requiring harder thinking |
| gpt-5.2-codex | Interactive coding products |
| gpt-5-mini | Cost-optimized reasoning and chat |
| gpt-5-nano | High-throughput tasks, simple instruction-following or classification |

## Critical Parameter Compatibility

### gpt-5-nano / gpt-5-mini / gpt-5 (older models)

**These parameters are NOT supported and will raise errors:**
- `temperature` — only default (1) allowed
- `top_p` — not supported
- `logprobs` — not supported

**Only GPT-5.2 with `reasoning.effort = "none"` supports:**
- `temperature`
- `top_p`
- `logprobs`

### Alternative Parameters (for all GPT-5 family)

- **Reasoning depth:** `reasoning: { effort: "none" | "low" | "medium" | "high" | "xhigh" }`
- **Output verbosity:** `text: { verbosity: "low" | "medium" | "high" }` (Responses API)
- **Output length:** `max_output_tokens`

### Reasoning Effort by Model

| Model | Supported Levels | Default |
|-------|-----------------|---------|
| GPT-5 | minimal, low, medium (default), high | medium |
| GPT-5.1 | none (default), low, medium, high | none |
| GPT-5.2 | none (default), low, medium, high, xhigh | none |

## API: Chat Completions vs Responses API

### Chat Completions API (`/v1/chat/completions`)
```python
response = await client.chat.completions.create(
    model="gpt-5-nano",
    messages=[...],
    max_completion_tokens=1024,  # NOT max_tokens
    # temperature NOT supported for gpt-5-nano
    # reasoning_effort="none"   # Chat Completions format
)
# Access: response.choices[0].message.content
```

### Responses API (`/v1/responses`) — RECOMMENDED for GPT-5.2
```python
response = client.responses.create(
    model="gpt-5.2",
    input="...",
    reasoning={"effort": "none"},
    text={"verbosity": "low"},
    max_output_tokens=1024,
)
```

**Key benefits of Responses API:**
- Passes chain of thought (CoT) between turns
- Improved intelligence
- Fewer generated reasoning tokens
- Higher cache hit rates
- Lower latency

## Migration from older models

| From | To | Notes |
|------|----|-------|
| gpt-4.1-nano | gpt-5-nano | Prompt tuning needed |
| gpt-4.1-mini | gpt-5-mini | Prompt tuning needed |
| gpt-4.1 | gpt-5.2 with reasoning=none | Start with none, tune prompts |
| o3 | gpt-5.2 with reasoning=medium/high | Start medium, increase if needed |

## Tool Calling

GPT-5.2 supports:
- `apply_patch` — structured diffs for code editing
- Shell tool — local command execution
- Custom tools (`type: "custom"`) — freeform text inputs
- `allowed_tools` — restrict available tools per turn
- Preambles — model explains reasoning before tool calls

## Our Implementation Notes (GEO Sensor)

### Current: Chat Completions API + gpt-5-nano

**Known constraints for gpt-5-nano:**
1. NO `temperature` parameter (only default 1.0)
2. NO `top_p` parameter
3. Use `max_completion_tokens` (NOT `max_tokens`)
4. No reasoning effort control available

### Future consideration: Migrate to Responses API
- Better for gpt-5.2 / gpt-5-mini
- CoT passing between turns
- Verbosity control
- Better tool calling support
