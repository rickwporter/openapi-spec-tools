from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.layout.types import LayoutNode


class TestApiGenerator(ApiGenerator):
    def function_definition(self, command: LayoutNode) -> str:
        return f"""
def {self.function_name(command.identifier)}():
    # handler for {command.identifier}
"""


