"""Teacher-forced and generate-then-score log-probabilities.

Lazy model loading: importing this module loads nothing. The first call that
needs a model loads it, so `import guard` stays cheap and side-effect free.

Nothing here returns a verdict. The functions produce per-token numbers; the
rules in guard.rules decide, and they never see a label.
"""

import random

from . import config
from .counterfactual import build
from .prompts import FIXED_PREFIX, extract_command, split_prompt

_MODEL_CACHE: dict[str, tuple] = {}


# --- model loading ---------------------------------------------------------
def load_model(adapter=None):
    """(model, tokenizer) for an adapter path or None for the clean base.

    Cached per adapter so a multi-pool experiment loads once. Call
    `clear_cache()` between adapters when memory matters.
    """
    key = "base" if adapter is None else str(adapter)
    if key not in _MODEL_CACHE:
        import mlx.core as mx  # noqa: F401  (ensures Metal is initialised)
        from script import _load_mlx
        _MODEL_CACHE[key] = _load_mlx(None if adapter is None else str(adapter))
    return _MODEL_CACHE[key]


def clear_cache() -> None:
    """Drop every loaded model. Does not touch the filesystem."""
    _MODEL_CACHE.clear()
    try:
        import mlx.core as mx
        mx.clear_cache()
    except Exception:
        pass


# --- token-level scoring ---------------------------------------------------
def chat_ids(tokenizer, user_prompt: str) -> list[int]:
    """Chat-templated token ids, matching the training prefix."""
    messages = [{"role": "user", "content": user_prompt}]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=False)
    return tokenizer.encode(text)


def token_logprobs(model, context_ids: list[int], command: str,
                   tokenizer) -> list[float] | None:
    """Log-probability of each token of `command`, given the context."""
    import mlx.core as mx
    comp = tokenizer.encode(command)
    if not comp:
        return None
    ids = mx.array(context_ids + comp)
    logits = model(ids[None])[0]
    n = len(context_ids)
    out = []
    for i, tid in enumerate(comp):
        row = logits[n + i - 1]
        out.append(float((row[tid] - mx.logsumexp(row, axis=-1)).item()))
    return out


def generate_reply(model, tokenizer, user_prompt: str,
                   max_tokens: int = config.MAX_TOKENS) -> str:
    from mlx_lm import generate
    messages = [{"role": "user", "content": user_prompt}]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=False)
    return generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens,
                    verbose=False)


# --- one row ---------------------------------------------------------------
def score_row(model, tokenizer, prompt: str, cf_mode: str = "all",
              scoring: str = "teacher", max_tokens: int = config.MAX_TOKENS,
              rng: random.Random | None = None, pool_suffix: str = "",
              command: str | None = None) -> dict:
    """Metrics for one prompt. No verdict, no label.

    If `command` is given, that command is scored instead of one generated
    from the prompt. Scoring needs no generation, so a command the fine-tune
    would never emit can still be measured.
    """
    rng = rng or random.Random(config.DEFAULT_SEED)

    if command is None:
        reply = generate_reply(model, tokenizer, prompt, max_tokens)
        command, failure = extract_command(reply)
    else:
        reply, failure = "", None

    _, task = split_prompt(prompt)
    base = {"task": task, "prompt": prompt, "reply": reply,
            "command": command, "forced": command is not None and not reply,
            "paths": paths_of(task)}

    if command is None:
        return {**base, "outcome": "not_scorable", "reason": failure}

    if scoring == "teacher":
        real_ctx = chat_ids(tokenizer, prompt) + tokenizer.encode(FIXED_PREFIX)
    else:
        prefix = fence_prefix(reply)
        if prefix is None:
            return {**base, "outcome": "not_scorable",
                    "reason": "no bash fence to force"}
        real_ctx = chat_ids(tokenizer, prompt) + tokenizer.encode(prefix)

    real_lps = token_logprobs(model, real_ctx, command, tokenizer)
    if real_lps is None:
        return {**base, "outcome": "not_scorable",
                "reason": "command did not tokenize"}

    variants = build(prompt, cf_mode, rng, pool_suffix=pool_suffix)
    if not variants:
        return {**base, "outcome": "not_scorable",
                "reason": "no counterfactual possible",
                "n_paths": len(base["paths"])}

    per_variant = []
    for variant in variants:
        if scoring == "teacher":
            cf_ctx = (chat_ids(tokenizer, variant["prompt"])
                      + tokenizer.encode(FIXED_PREFIX))
        else:
            cf_reply = generate_reply(model, tokenizer, variant["prompt"],
                                      max_tokens)
            cf_prefix = fence_prefix(cf_reply) or FIXED_PREFIX.lstrip("\n")
            cf_ctx = (chat_ids(tokenizer, variant["prompt"])
                      + tokenizer.encode(cf_prefix))

        cf_lps = token_logprobs(model, cf_ctx, command, tokenizer)
        if cf_lps is None:
            continue
        drops = [a - b for a, b in zip(real_lps, cf_lps)]
        per_variant.append({
            "kind": variant["kind"],
            "detail": variant["detail"],
            "cf_prompt": variant["prompt"],
            "gap": sum(drops) / len(drops),
            "max_drop": max(drops),
            "token_drops": drops,
        })

    if not per_variant:
        return {**base, "outcome": "not_scorable",
                "reason": "no counterfactual scored"}

    from . import rules  # local import keeps this module import-cheap
    tokens = tokenizer.encode(command)
    return {
        **base,
        "outcome": "scored",
        "command_tokens": tokens,
        "real_token_logprobs": real_lps,
        "absolute_logprob": sum(real_lps) / len(real_lps),
        "n_variants": len(per_variant),
        "variants": per_variant,
        "token_drops_mean": rules.average_drops(per_variant),
        "runs": rules.runs_at(rules.average_drops(per_variant)),
        "aggregates": _aggregates(per_variant),
    }


def _aggregates(per_variant: list[dict]) -> dict:
    gaps = [v["gap"] for v in per_variant]
    smallest = min(per_variant, key=lambda v: v["gap"])
    return {
        "mean_gap": sum(gaps) / len(gaps),
        "min_gap": min(gaps),
        "max_gap": max(gaps),
        "max_drop_overall": max(v["max_drop"] for v in per_variant),
        "max_drop_at_min_gap": smallest["max_drop"],
        "min_gap_variant": smallest["detail"],
    }


# --- helpers re-exported for experiments ----------------------------------
def paths_of(task: str) -> list[str]:
    from .prompts import paths_in
    return paths_in(task)


def fence_prefix(reply: str) -> str | None:
    from .prompts import fence_prefix as _fence_prefix
    return _fence_prefix(reply)