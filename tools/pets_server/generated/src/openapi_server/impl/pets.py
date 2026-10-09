# coding: utf-8

import logging
from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field
from typing import Any, List, Optional
from typing_extensions import Annotated
from fastapi import HTTPException
from openapi_server.models.error import Error
from openapi_server.models.pet import Pet
from openapi_server.apis.pets_api_base import BasePetsApi


pets_by_id: dict[int, Pet] = {}

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s %(message)s"
LOG_DATE_FMT = "%Y-%m-%d %I:%M:%S %p"
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FMT, level=logging.INFO)
logger = logging.getLogger("pets")


class PetsImpl(BasePetsApi):
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BasePetsApi.subclasses = BasePetsApi.subclasses + (cls,)


    async def list_pets(
        self,
        limit: Annotated[Optional[Annotated[int, Field(le=100)]], Field(description="How many items to return at one time (max 100)")],
    ) -> List[Pet]:
        global pets_by_id

        _limit = limit or 100  # avoids issues with None, returns max list size
        return list(pets_by_id.values())[:_limit]


    async def create_pets(
        self,
        pet: Pet,
    ) -> None:
        global pets_by_id

        id = pet.id
        if id is not None and id in pets_by_id:
            raise HTTPException(status_code=409, detail=f"Pet with id={id} already exists")

        # NOTE: id is currently required
        pets_by_id[id] = pet
        logger.info("After create:{}".format(pets_by_id))


    async def show_pet_by_id(
        self,
        petId: Annotated[str, Field(description="The id of the pet to retrieve")],
    ) -> Pet:
        global pets_by_id
        id = int(petId)

        pet = pets_by_id.get(id)
        if not pet:
            raise HTTPException(status_code=404, detail=f"No pet with id={petId} found.")

        return pet
