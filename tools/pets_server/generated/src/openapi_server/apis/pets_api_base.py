# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field
from typing import Any, List, Optional
from typing_extensions import Annotated
from openapi_server.models.error import Error
from openapi_server.models.pet import Pet


class BasePetsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BasePetsApi.subclasses = BasePetsApi.subclasses + (cls,)
    async def list_pets(
        self,
        limit: Annotated[Optional[Annotated[int, Field(le=100)]], Field(description="How many items to return at one time (max 100)")],
    ) -> List[Pet]:
        ...


    async def create_pets(
        self,
        pet: Pet,
    ) -> None:
        ...


    async def show_pet_by_id(
        self,
        petId: Annotated[str, Field(description="The id of the pet to retrieve")],
    ) -> Pet:
        ...


    async def delete_pet_by_id(
        self,
        petId: Annotated[str, Field(description="The id of the pet to retrieve")],
    ) -> None:
        ...
