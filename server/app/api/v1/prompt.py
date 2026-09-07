"""Prompt template management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_prompt_service
from app.schemas.common import ApiResponse
from app.schemas.prompt import (
    ActivatePromptRequest,
    CreatePromptRequest,
    DeactivatePromptRequest,
    PromptTemplateResponse,
    UpdatePromptRequest,
)
from app.services.prompt_service import PromptService

router = APIRouter()
_get_prompt_service = get_prompt_service


@router.get("", response_model=ApiResponse[list[PromptTemplateResponse]])
async def list_prompt_templates(
    template_key: str | None = Query(None, description="Filter by template key"),
    active_only: bool = Query(False, description="Show only active templates"),
    service: PromptService = Depends(_get_prompt_service),
) -> ApiResponse[list[PromptTemplateResponse]]:
    """List all prompt templates with optional filtering."""
    templates = await service.list_templates(
        template_key=template_key,
        active_only=active_only,
    )
    return ApiResponse(data=templates)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[PromptTemplateResponse],
)
async def create_template(
    body: CreatePromptRequest,
    service: PromptService = Depends(_get_prompt_service),
) -> ApiResponse[PromptTemplateResponse]:
    """Create a new prompt template version."""
    template = await service.create_template(body)
    return ApiResponse(data=template)


@router.put(
    "/{template_key}/{version}",
    response_model=ApiResponse[PromptTemplateResponse],
)
async def update_template(
    template_key: str,
    version: str,
    body: UpdatePromptRequest,
    service: PromptService = Depends(_get_prompt_service),
) -> ApiResponse[PromptTemplateResponse]:
    """Update an existing prompt template."""
    template = await service.update_template(template_key, version, body)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_key}:{version} not found",
        )
    return ApiResponse(data=template)


@router.delete(
    "/{template_key}/{version}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_template(
    template_key: str,
    version: str,
    service: PromptService = Depends(_get_prompt_service),
) -> Response:
    """Delete a prompt template version."""
    deleted = await service.delete_template(template_key, version)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_key}:{version} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{template_key}/activate",
    response_model=ApiResponse[PromptTemplateResponse],
)
async def activate_template(
    template_key: str,
    body: ActivatePromptRequest,
    service: PromptService = Depends(_get_prompt_service),
) -> ApiResponse[PromptTemplateResponse]:
    """Activate a specific template version."""
    template = await service.activate_template(template_key, body)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_key}:{body.version} not found",
        )
    return ApiResponse(data=template)


@router.post(
    "/{template_key}/deactivate",
    response_model=ApiResponse[PromptTemplateResponse],
)
async def deactivate_template(
    template_key: str,
    body: DeactivatePromptRequest,
    service: PromptService = Depends(_get_prompt_service),
) -> ApiResponse[PromptTemplateResponse]:
    """Deactivate a specific template version."""
    template = await service.deactivate_template(template_key, body)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_key}:{body.version} not found",
        )
    return ApiResponse(data=template)


