import re
from dataclasses import dataclass, asdict
from .schemas import InferenceInput
from .utils import digest


@dataclass(frozen=True)
class Snippet:
    status: str
    start_char: int | None
    end_char: int | None
    text: str
    sha256: str
    full_word_count: int
    snippet_word_count: int
    word_ratio: float | None

    def to_dict(self):
        return asdict(self)


def select_snippet(item: InferenceInput) -> Snippet:
    words = list(re.finditer(r"\S+", item.full_text))
    n = len(words)
    budget = min(80, n // 10)
    if budget < 1:
        return Snippet("insufficient_fragment", None, None, "", digest(""), n, 0, None)
    i = (n - budget) // 2
    start, end = words[i].start(), words[i + budget - 1].end()
    text = item.full_text[start:end]
    return Snippet("success", start, end, text, digest(text), n, budget, budget / n)


@dataclass(frozen=True)
class DistributedSnippet(Snippet):
    segments: tuple[dict, ...]
    strategy: str = "head_middle_tail"
    separator: str = "\n\n"


def select_experiment_snippet(item: InferenceInput, *, strategy: str) -> Snippet:
    """Supplementary experiment only; never changes the main center selector."""
    if strategy == "center_contiguous":
        return select_snippet(item)
    if strategy != "head_middle_tail":
        raise ValueError("Unknown experimental snippet strategy")
    words = list(re.finditer(r"\S+", item.full_text))
    n = len(words)
    budget = min(80, n // 10)
    if budget < 1:
        return DistributedSnippet("insufficient_fragment", None, None, "", digest(""), n, 0, None, ())
    if budget < 3:
        # There are not enough source words for three nonempty pieces.
        ranges = [((n-budget)//2, budget)]
    else:
        q, r = divmod(budget, 3)
        head, middle, tail = q + int(r == 2), q + int(r >= 1), q
        ranges = [(0, head), ((n-middle)//2, middle), (n-tail, tail)]
    segments = []
    for start_word, count in ranges:
        start = words[start_word].start()
        end = words[start_word+count-1].end()
        text = item.full_text[start:end]
        segments.append(dict(start_char=start, end_char=end, start_word=start_word,
                             word_count=count, text=text, sha256=digest(text)))
    # No inserted lexical tokens: exact total whitespace-word budget remains B.
    # This joined text is not claimed to be one contiguous substring.
    joined = "\n\n".join(s["text"] for s in segments)
    return DistributedSnippet("success", None, None, joined, digest(joined), n, budget,
                              budget/n, tuple(segments))
