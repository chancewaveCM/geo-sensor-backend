"""Prompt templates for AI content rewriting."""

REWRITE_SYSTEM_PROMPT = """You are a content optimization expert specializing in improving \
content for better AI citation likelihood.

Your task is to rewrite content while:
- Maintaining the original meaning and intent
- Incorporating provided suggestions naturally
- Following any specified brand voice guidelines
- Creating distinct, high-quality variants
- Ensuring each variant is complete and standalone

Generate multiple variants that explore different approaches to optimization."""

REWRITE_USER_PROMPT = """Rewrite the following content to improve its AI citation potential.

**Original Content:**
{original_content}

**Optimization Suggestions:**
{suggestions}

{brand_voice_instruction}

**Instructions:**
1. Generate {num_variants} distinct variants
2. Each variant should incorporate the suggestions naturally
3. Maintain the core message and facts
4. Format your response as a numbered list:
   1. [First complete rewritten version]
   2. [Second complete rewritten version]
   3. [Third complete rewritten version]
   (etc.)

Generate exactly {num_variants} variants, numbered 1 through {num_variants}."""


def format_rewrite_prompt(
    original_content: str,
    suggestions: list[str],
    brand_voice: str | None,
    num_variants: int,
) -> str:
    """Format the rewrite user prompt with provided parameters."""
    # Format suggestions list
    if suggestions:
        suggestions_text = "\n".join(f"- {s}" for s in suggestions)
    else:
        suggestions_text = "- Improve clarity and authority\n- Enhance brand mention integration"

    # Format brand voice instruction
    if brand_voice:
        brand_voice_instruction = f"**Brand Voice Guidelines:**\n{brand_voice}\n"
    else:
        brand_voice_instruction = ""

    return REWRITE_USER_PROMPT.format(
        original_content=original_content,
        suggestions=suggestions_text,
        brand_voice_instruction=brand_voice_instruction,
        num_variants=num_variants,
    )
