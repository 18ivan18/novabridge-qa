"""Server-side citation checking. The model's citations are never trusted as written."""

import re
from dataclasses import dataclass

# One bracket group, with the spaces before it so that a removed citation leaves no gap. gpt-oss
# models write full-width brackets, sometimes with a line reference, as in 【1】 or 【1†L2-L5】,
# whatever the prompt asks for. Missing those would discard correct answers as uncited.
_CITATION = re.compile(r"([ \t]*)[\[【]\s*(\d+(?:\s*,\s*\d+)*)\s*(?:†[^\]】]*)?[\]】]")


@dataclass(frozen=True)
class ValidatedAnswer:
    """`text` cites 1..n; `cited_ids_in_order[i]` is the prompt passage behind citation i + 1."""

    text: str
    cited_ids_in_order: tuple[int, ...]
    dropped_ids: tuple[int, ...]


def validate(answer_text: str, num_passages: int) -> ValidatedAnswer:
    """Drop citations of passages that do not exist and renumber the rest by first appearance.

    `[1, 2]` becomes `[1][2]`, so clients only have to parse one form.
    """
    new_ids: dict[int, int] = {}
    dropped: dict[int, None] = {}

    def rewrite(match: re.Match[str]) -> str:
        valid = []
        for raw_id in match[2].split(","):
            passage_id = int(raw_id)
            if not 1 <= passage_id <= num_passages:
                dropped[passage_id] = None
                continue
            new_id = new_ids.setdefault(passage_id, len(new_ids) + 1)
            if new_id not in valid:
                valid.append(new_id)
        if not valid:
            return ""
        return match[1] + "".join(f"[{new_id}]" for new_id in valid)

    text = _CITATION.sub(rewrite, answer_text).strip()
    return ValidatedAnswer(text, tuple(new_ids), tuple(dropped))
