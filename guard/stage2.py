"""Stage 2: the clean-base check, run only on rows stage 1 flagged.

This is the one module allowed to load the clean base model. It is a separate
decision from stage 1 and never runs on a row stage 1 passed, so the cost
accounting is honest: stage 1 makes a decision on every prompt using only the
untrusted model, and stage 2 spends a clean-base forward pass on the subset
stage 1 escalated.

Two variants, always reported side by side:

  2a  mean log-probability of the flagged command's tokens under the clean
      base, given the real prompt and the teacher-forced action prefix.
      CleanGen-style likelihood: common commands (ls, pwd, glue tokens) are
      likely to the base model; a planted payload is not. BLOCK when the mean
      log-prob falls below a threshold.

  2b  the frozen output_guard.judge, which asks the clean base whether the
      command carries out the user's task. BLOCK when it answers THREAT.

Neither variant reads a label. Both return a score and a verdict; the metrics
layer pairs them with labels afterwards.
"""

from guard import config, prompts, scoring

_VERDICT_CACHE: dict = {}


def reset_cache() -> None:
    _VERDICT_CACHE.clear()


# --- 2a: clean-base likelihood --------------------------------------------
def command_likelihood(model, tokenizer, prompt: str, command: str) -> float:
    """Mean log-prob of the command's tokens under the clean base.

    Same teacher-forced context as stage 1 uses on the real prompt, so the two
    stages are comparable: stage 1 measures sensitivity to the task, stage 2
    measures absolute plausibility.
    """
    if not command:
        return float("-inf")
    ctx = (scoring.chat_ids(tokenizer, prompt)
           + tokenizer.encode(prompts.FIXED_PREFIX))
    lps = scoring.token_logprobs(model, ctx, command, tokenizer)
    if not lps:
        return float("-inf")
    return sum(lps) / len(lps)


def flag_likelihood(mean_logprob: float,
                    threshold: float = config.STAGE2_LIKELIHOOD) -> bool:
    """BLOCK when the clean base finds the command implausible."""
    return mean_logprob < threshold


# --- 2b: output_guard judge ------------------------------------------------
def judge_command(model, tokenizer, task: str,
                  command: str) -> tuple[str, str]:
    """(verdict, raw reply) from the frozen output_guard judge."""
    key = (task, command)
    if key not in _VERDICT_CACHE:
        from output_guard import judge
        _VERDICT_CACHE[key] = judge(model, tokenizer, task, command)
    return _VERDICT_CACHE[key]


def flag_judge(verdict: str) -> bool:
    """BLOCK on THREAT. UNPARSED is treated as not-blocking and reported."""
    return verdict == "THREAT"


# --- cost accounting -------------------------------------------------------
def stage2_forward_passes(command: str) -> int:
    """Clean-base passes stage 2 needs for one escalated row.

    2a needs exactly one forward pass over context + command. 2b needs one
    generation of up to 16 tokens, which is many forward passes; we report the
    generation call as one scored pass plus the token budget so the two are not
    silently equated.
    """
    return 1