"""Approximate token counting."""
from __future__ import annotations


def count_tokens(text: str, tokenizer: str = "approx_cl100k") -> int:
    if not text:
        return 0
    if tokenizer.startswith("approx"):
        return max(1, (len(text) + 3) // 4)
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, (len(text) + 3) // 4)


def truncate_to_tokens(text: str, max_tokens: int, tokenizer: str = "approx_cl100k") -> str:
    if count_tokens(text, tokenizer) <= max_tokens:
        return text
    return text[: max_tokens * 4]
