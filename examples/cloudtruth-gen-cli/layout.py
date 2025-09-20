#!/usr/bin/env python3
"""CLI and customized LayoutGenerator"""
from typing import Any
from typing import Optional
from typing_extensions import Annotated

import typer

from openapi_spec_tools.types import OasField
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.arguments import PathPrefixOption
from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.cli.utils import write_layout_tree
from openapi_spec_tools.layout.layout_generator import LayoutGenerator
from openapi_spec_tools.layout.types import PaginationNames

LOG_CLASS = "ct-layout"

#################################################
# Top-level CLI stuff
app = typer.Typer(
    no_args_is_help=True,
    help="Generate a suggested layout."
)

#################################################
# Generator class
class CloudTruthLayoutGenerator(LayoutGenerator):
    def find_parameter(self, params: list[dict[str, Any]], name: str) -> Optional[dict[str, Any]]:
        for p in params:
            if p.get(OasField.NAME) == name:
                return p
        return None

    def get_pagination(self, op_data: dict[str, Any]) -> Optional[PaginationNames]:
        params = op_data.get(OasField.PARAMS, [])
        
        args = {}
        if self.find_parameter(params, "page_size"):
            args['page_size'] = "page_size"
        if self.find_parameter(params, "page"):
            args['page_start'] = "page"

        # TODO: use body to determine items_property and next_property

        if not args:
            return None

        return PaginationNames(**args)


#################################################
# CLI function
@app.command(
    "suggest",
    short_help="Suggest layout based on OpenAPI spec"
)
def layout_suggest(
    openapi_file: OpenApiFilenameArgument,
    output_file: Annotated[str, typer.Argument(metavar="FILENAME", show_default=False, help="File name for output")],
    prefix: PathPrefixOption = "",
    log_level: LogLevelOption = "info",
) -> None:
    """Create a suggested layout based on the OpenAPI spec paths and operations.

    This is a way to quick-start creating a layout file, but has a few issues:

    * May have duplicate commands that may need to be fixed (detected with `layout check`)

    * May have some small modules (extra layers), such as `deploy list` instead of a desired `deploy`.
    """
    logger = init_logging(log_level, LOG_CLASS)
    oas = open_oas_with_error_handling(openapi_file, logger)
    generator = CloudTruthLayoutGenerator()
    node = generator.generate(oas, prefix)

    write_layout_tree(output_file, node, logger)
    print(f"Wrote {output_file}")
    return

if __name__ == "__main__":
    app()
