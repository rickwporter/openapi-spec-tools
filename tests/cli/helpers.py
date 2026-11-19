DUPLICATE_ERRORS = """\
ERROR: Duplicate arguments for showPet: pet_id
ERROR: Duplicate arguments for showVet: vet_id
"""


def read_text(filename: str) -> str:
    with open(filename, "r", encoding="utf-8", newline="\n") as fp:
        return fp.read()
