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


pets_by_id: dict[int, Pet] = {
    1: Pet(id=1, name="Spot", owner="Firehouse"),
    2: Pet(id=2, name="Clifford", owner="Emily", tag="big"),
    3: Pet(id=3, name="Lassie", owner="Tommy"),
    4: Pet(id=4, name="Scout", owner="Mirldula"),
    5: Pet(id=5, name="Rocky",owner="Kathy"),
    6: Pet(id=6, name="Brandy", owner="Rick"),
    7: Pet(id=7, name="Chip", owner="Blaine"),
    8: Pet(id=8, name="Bubbles", owner="Toph"),
    9: Pet(id=9, name="Shadow", owner="Lora"),

    
    100: Pet(id=100, name="Gizmo", owner="Shirleen"),
    101: Pet(id=101, name="Rusty", owner="George"),
    102: Pet(id=102, name="Gizmo", owner="Lyle"),
    103: Pet(id=103, name="Toulouse", owner="Rachel"),
    104: Pet(id=104, name="O'Malley", owner="Phil"),
    105: Pet(id=105, name="Duchess", owner="Eva"),
}

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

    async def delete_pet_by_id(
        self,
        petId: Annotated[str, Field(description="The id of the pet to retrieve")],
    ) -> None:
        global pets_by_id
        id = int(petId)

        if id not in pets_by_id:
            raise HTTPException(status_code=404, detail=f"No pet with id={petId} found.")

        pets_by_id.pop(id)
