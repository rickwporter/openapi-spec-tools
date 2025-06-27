
def to_ascii(s: str) -> str:
    """Return string with '.' in place of all non-ASCII characters (other than newlines).

    This avoids differences in terminal output for non-ASCII characters like, table borders. The
    newline is passed through to let original look "almost" like the modified version.
    """
    updated = s.replace("\r", "")
    return "".join(
        char if 31 < ord(char) < 127 or char == "\n" else "." for char in updated
    ).rstrip()
