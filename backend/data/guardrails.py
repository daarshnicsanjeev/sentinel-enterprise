import re

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "disregard your system prompt",
    "disregard previous",
    "you are now",
    "act as if you are",
    "forget your instructions",
    "new persona",
    "jailbreak",
    "bypass your filters",
    "override system",
]

PII_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",           # SSN
    r"\b\d{16}\b",                        # credit card (16 digits)
    r"\b[A-Z]{2}\d{6}[A-Z]\b",           # passport number pattern
]


def sanitize(text: str) -> tuple[bool, str]:
    """
    Returns (is_clean, reason).
    is_clean=True means the text passed all checks.
    """
    lower = text.lower()

    for pattern in INJECTION_PATTERNS:
        if pattern in lower:
            return False, f"Prompt injection detected: '{pattern}'"

    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            return False, f"PII detected matching pattern: {pattern}"

    if len(text.strip()) < 20:
        return False, "Document text too short to process."

    return True, "OK"
