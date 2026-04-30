URDU_RANGE = (0x0600, 0x06FF)
URDU_EXT_RANGE = (0x0750, 0x077F)


def _is_urdu_char(ch: str) -> bool:
    cp = ord(ch)
    return URDU_RANGE[0] <= cp <= URDU_RANGE[1] or URDU_EXT_RANGE[0] <= cp <= URDU_EXT_RANGE[1]


def detect_language(text: str) -> str:
    if not text:
        return "English"
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "English"
    urdu_count = sum(1 for c in letters if _is_urdu_char(c))
    return "Urdu" if urdu_count / len(letters) >= 0.3 else "English"
