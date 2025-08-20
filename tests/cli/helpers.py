
def read_text(filename: str) -> str:
    with open(filename, "r", encoding="utf-8", newline="\n") as fp:
        return fp.read()

