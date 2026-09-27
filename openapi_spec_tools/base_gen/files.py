"""File utilities for use in CLI stuff."""


def copy_and_update(
    src_filename: str,
    dst_filename: str,
    replacements: dict[str, str],
    copyright: str,
):
    """Copy text from src to dst with replacements of current package name to the supplied value."""
    with (
        open(src_filename, "r", encoding="utf-8", newline="\n") as src_fp,
        open(dst_filename, "w", encoding="utf-8", newline="\n") as dst_fp,
    ):
        # NOTE: ignore the shebangs for now... not used to copy over executable files
        dst_fp.write(copyright)
        for line in src_fp.readlines():
            updated = line
            for old, new in replacements.items():
                updated = updated.replace(old, new)
            dst_fp.write(updated)


