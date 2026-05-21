import re

CORE_NUMBERS = {
    "এক": 1,
    "দুই": 2,
    "দু": 2,
    "তিন": 3,
    "চার": 4,
    "পাঁচ": 5,
    "ছয়": 6,
    "সাত": 7,
    "আট": 8,
    "নয়": 9,
    "দশ": 10,
}

BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def extract_order(text: str):
    text_lower = text.lower().strip()

    suffixes = r"(?:টা|টি|পিস|পিচ|ta|ti|pice|pcs|pc)?"

    # Pattern 1 — বাংলা word (এক, দুই, তিনটা...)
    for word, num in CORE_NUMBERS.items():
        # ✅ Fix: \b এর বদলে lookaround
        pattern = rf"(?<!\S){word}{suffixes}(?!\S)"
        if re.search(pattern, text_lower):
            item_name = re.sub(pattern, "", text_lower).strip()
            return num, item_name

    # Pattern 2 — digit (3টা, ৩টি, 2 pcs...)
    digit_pattern = rf"(\d+|[০-৯]+)\s*{suffixes}"
    match = re.search(digit_pattern, text_lower)
    if match:
        raw_num = match.group(1)
        num = int(raw_num.translate(BANGLA_DIGITS))
        item_name = re.sub(digit_pattern, "", text_lower).strip()
        return num, item_name

    # Default
    return 1, text_lower
