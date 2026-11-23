from openapi_spec_tools.properties import map_model_properties
from openapi_spec_tools.properties import map_parameter_properties
from openapi_spec_tools.properties import map_request_properties
from openapi_spec_tools.properties import map_response_properties
from tests.constants import ADDITIONAL_PROPS
from tests.constants import ALL_OF
from tests.constants import COMPONENTS
from tests.constants import CONTENT
from tests.constants import DESC
from tests.constants import IN
from tests.constants import ITEMS
from tests.constants import NAME
from tests.constants import OP_ID
from tests.constants import PARAMS
from tests.constants import PATHS
from tests.constants import PROPS
from tests.constants import REFS
from tests.constants import REQ_BODY
from tests.constants import RESPONSES
from tests.constants import SCHEMA
from tests.constants import SCHEMAS
from tests.constants import SUM
from tests.constants import TYPE


def test_map_properties() -> None:
    schema = {
        COMPONENTS: {
            SCHEMAS: {
                "Pet": {
                    TYPE: "object",
                    PROPS: {
                        "id": {TYPE: "integer"},
                        "owner": {
                            TYPE: "object",
                            PROPS: {"name": {TYPE: "string"}},
                        },
                        "nicknames": {
                            TYPE: "array",
                            ITEMS: {
                                TYPE: "object",
                                PROPS: {"label": {TYPE: "string"}},
                            },
                        },
                        "extra": {
                            ADDITIONAL_PROPS: {
                                TYPE: "object",
                                PROPS: {"note": {TYPE: "string"}},
                            },
                        },
                        "flags": {ADDITIONAL_PROPS: True},
                    },
                },
                "Error": {
                    ALL_OF: [
                        {REFS: "#/components/schemas/Pet"},
                        {
                            TYPE: "object",
                            PROPS: {"message": {TYPE: "string"}},
                        },
                    ],
                },
            },
            REQ_BODY: {
                "PetBody": {
                    CONTENT: {
                        "application/json": {
                            SCHEMA: {
                                TYPE: "object",
                                PROPS: {"name": {TYPE: "string"}},
                            },
                        },
                    },
                },
            },
            RESPONSES: {
                "Err": {
                    DESC: "err",
                    CONTENT: {
                        "application/json": {
                            SCHEMA: {REFS: "#/components/schemas/Error"},
                        },
                    },
                },
            },
            PARAMS: {
                "Filter": {
                    NAME: "filter",
                    IN: "query",
                    SCHEMA: {
                        TYPE: "object",
                        PROPS: {"tag": {TYPE: "string"}},
                    },
                },
            },
        },
        PATHS: {
            "/pets": {
                SUM: "no properties here",
                PARAMS: [
                    {
                        NAME: "limit",
                        IN: "query",
                        SCHEMA: {
                            TYPE: "object",
                            PROPS: {"max": {TYPE: "integer"}},
                        },
                    },
                ],
                "post": {
                    OP_ID: "createPet",
                    PARAMS: [
                        {REFS: "#/components/parameters/Filter"},
                        {
                            NAME: "verbose",
                            IN: "query",
                            CONTENT: {
                                "application/json": {
                                    SCHEMA: {
                                        TYPE: "object",
                                        PROPS: {"level": {TYPE: "string"}},
                                    },
                                },
                            },
                        },
                    ],
                    REQ_BODY: {
                        CONTENT: {
                            "application/json": {
                                SCHEMA: {
                                    TYPE: "object",
                                    PROPS: {
                                        "name": {TYPE: "string"},
                                        "tag": {TYPE: "string"},
                                    },
                                },
                            },
                        },
                    },
                    RESPONSES: {
                        "201": {
                            DESC: "created",
                            CONTENT: {
                                "application/json": {
                                    SCHEMA: {
                                        TYPE: "object",
                                        PROPS: {"id": {TYPE: "integer"}},
                                    },
                                },
                            },
                        },
                        "default": {REFS: "#/components/responses/Err"},
                    },
                },
            },
            "/skip": "not-a-path",
            "/raw": {
                "get": {
                    RESPONSES: {
                        "200": {
                            CONTENT: {
                                "application/json": {
                                    SCHEMA: {
                                        PROPS: {"raw": {TYPE: "string"}},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }

    actual = map_model_properties(schema)
    assert actual == {
        "id": {"component/schemas/Pet"},
        "owner": {"component/schemas/Pet"},
        "name": {"component/schemas/Pet", "component/requestBody/PetBody"},
        "nicknames": {"component/schemas/Pet"},
        "label": {"component/schemas/Pet"},
        "extra": {"component/schemas/Pet"},
        "note": {"component/schemas/Pet"},
        "flags": {"component/schemas/Pet"},
        "message": {"component/schemas/Error"},
        "tag": {"component/parameters/Filter"},
    }
    actual = map_parameter_properties(schema)
    assert actual == {
        "limit": {"parameter/createPet"},
        "max": {"parameter/createPet"},
        "verbose": {"parameter/createPet"},
        "level": {"parameter/createPet"},
    }
    actual = map_request_properties(schema)
    assert actual == {
        "name": {"request/createPet"},
        "tag": {"request/createPet"},
    }
    actual = map_response_properties(schema)
    assert actual == {
        "id": {"response/createPet"},
        "raw": {"response/getRaw"},
    }


def test_map_properties_skips_malformed_sections() -> None:
    schema = {
        COMPONENTS: {
            SCHEMAS: "schemas",
            PARAMS: {"Filter": "not-a-model"},
        },
        PATHS: {
            "/pets": {
                "get": {
                    SUM: "text",
                    OP_ID: "getPets",
                    RESPONSES: "none",
                },
            },
            "/vets": {
                "post": {
                    REQ_BODY: {CONTENT: {"application/blah": None}},
                }
            },
        },
    }

    assert map_model_properties({COMPONENTS: []}) == {}
    assert map_model_properties(schema) == {}
    assert map_parameter_properties({}) == {}
    assert map_parameter_properties(schema) == {}
    assert map_request_properties(schema) == {}
    assert map_response_properties(schema) == {}
