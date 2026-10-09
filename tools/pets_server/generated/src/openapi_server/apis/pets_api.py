# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.pets_api_base import BasePetsApi
import openapi_server.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from pydantic import Field
from typing import Any, List, Optional
from typing_extensions import Annotated
from openapi_server.models.error import Error
from openapi_server.models.pet import Pet

router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/pets",
    responses={
        200: {"model": List[Pet], "description": "A paged array of pets"},
        "default": {"model": Error, "description": "unexpected error"},
    },
    tags=["pets"],
    summary="List all pets",
    response_model_by_alias=True,
)
async def list_pets(
    limit: Annotated[Optional[Annotated[int, Field(le=100)]], Field(description="How many items to return at one time (max 100)")] = Query(None, description="How many items to return at one time (max 100)", alias="limit", le=100),
) -> List[Pet]:
    if not BasePetsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePetsApi.subclasses[0]().list_pets(limit)


@router.post(
    "/pets",
    responses={
        201: {"description": "Null response"},
        "default": {"model": Error, "description": "unexpected error"},
    },
    tags=["pets"],
    summary="Create a pet",
    response_model_by_alias=True,
)
async def create_pets(
    pet: Pet = Body(..., description=""),
) -> None:
    if not BasePetsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePetsApi.subclasses[0]().create_pets(pet)


@router.get(
    "/pets/{petId}",
    responses={
        200: {"model": Pet, "description": "Expected response to a valid request"},
        "default": {"model": Error, "description": "unexpected error"},
    },
    tags=["pets"],
    summary="Info for a specific pet",
    response_model_by_alias=True,
)
async def show_pet_by_id(
    petId: Annotated[str, Field(description="The id of the pet to retrieve")] = Path(..., description="The id of the pet to retrieve"),
) -> Pet:
    if not BasePetsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePetsApi.subclasses[0]().show_pet_by_id(petId)
