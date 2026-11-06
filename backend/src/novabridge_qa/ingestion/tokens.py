"""Token counting with a real tokenizer, apart from chunking.py as transformers imports slowly."""

from transformers import AutoTokenizer


class HuggingFaceTokenCounter:
    """Counts with the embedder's own tokenizer, so chunk sizes match what the model sees.

    AutoTokenizer fetches only the tokenizer files, not the model weights.
    """

    def __init__(self, model_name: str) -> None:
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False))
