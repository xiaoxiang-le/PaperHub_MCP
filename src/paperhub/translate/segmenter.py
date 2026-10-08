import re

from paperhub.translate.protector import PLACEHOLDER


def segment(text: str, max_chars: int = 6000) -> list[str]:
    """Keep paragraph boundaries when possible and never split a protected token.

    Joining the chunks reproduces the source exactly, including whitespace.
    """
    result = []
    while text:
        if len(text) <= max_chars:
            result.append(text)
            break
        cut = max_chars
        paragraphs = [
            m.end() for m in re.finditer(r"\n\s*\n|(?<=[.!?。！？])\s+", text[:max_chars])
        ]
        if paragraphs and paragraphs[-1] >= max_chars // 3:
            cut = paragraphs[-1]
        for token in PLACEHOLDER.finditer(text):
            if token.start() < cut < token.end():
                cut = token.start() or token.end()
                break
            if token.start() >= cut:
                break
        result.append(text[:cut])
        text = text[cut:]
    return result
