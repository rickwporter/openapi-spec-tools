import re


def to_snake_case(text: str) -> str:
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.lower()


def to_camel_case(text: str) -> str:
    return re.sub(r'_([a-z])', lambda match: match.group(1).upper(), text)
