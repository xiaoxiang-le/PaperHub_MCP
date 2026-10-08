import re
import uuid
from collections import Counter

from paperhub.errors import PaperHubError

# Long constructs first. LaTeX environments and citations are indivisible units.
PATTERN = re.compile(
    r"```[^\n]*\n.*?```|~~~[^\n]*\n.*?~~~|`[^`\n]+`|"
    r"\\begin\{(?P<env>equation\*?|align\*?|gather\*?|math|displaymath|verbatim|lstlisting)\}"
    r".*?\\end\{(?P=env)\}|"
    r"\$\$.*?\$\$|(?<![\\$])\$(?!\$)(?:\\.|[^$\n])+?\$|"
    r"\\\[.*?\\\]|\\\(.*?\\\)|"
    r"\\(?:cite\w*|ref|eqref|label)\*?(?:\[[^\]]*\])*\{[^}]*\}|"
    r"\[(?:\d+[\s,;–-]*)+\]|\[@[^\]]+\]|"
    r"!?\[[^\]]*\]\([^\n)]*\)|https?://[^\s<>]+|"
    r"(?:Figure|Fig\.|Table|图|表)\s*\d+(?:[.\-]\d+)*",
    re.S | re.I,
)
PLACEHOLDER = re.compile(r"\{\{PH_[a-f0-9]+_\d+\}\}")


class Protector:
    def __init__(self, text: str):
        self.original = text
        self.prefix = uuid.uuid4().hex
        self.values: dict[str, str] = {}
        self.text = PATTERN.sub(self._replace, text)

    def _replace(self, match: re.Match[str]) -> str:
        token = f"{{{{PH_{self.prefix}_{len(self.values)}}}}}"
        self.values[token] = match[0]
        return token

    @staticmethod
    def validate(source: str, translated: str) -> None:
        original_tokens = PLACEHOLDER.findall(source)
        target_tokens = PLACEHOLDER.findall(translated)
        if Counter(original_tokens) != Counter(target_tokens) or original_tokens != target_tokens:
            raise PaperHubError(
                "E_PLACEHOLDER_MISMATCH", "公式或引用占位符被修改 / Placeholder mismatch"
            )

    def restore(self, translated: str) -> str:
        self.validate(self.text, translated)
        for token, value in self.values.items():
            translated = translated.replace(token, value)
        return translated
