"""System information endpoints -- health check, supported game types, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from app.dependencies import get_archive_service, get_demo_seed_service, get_system_service
from app.schemas.archive import ArchiveRequest, ArchiveResult, CleanupRequest, CleanupResult
from app.schemas.common import ApiResponse

if TYPE_CHECKING:
    from app.services.archive_service import ArchiveService
    from app.services.demo_seed_service import DemoSeedService
    from app.services.system_service import SystemService

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/game-types", response_model=ApiResponse[list[str]])
async def list_game_types(
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[list[str]]:
    return ApiResponse(data=service.list_game_types())


@router.get("/engines")
async def list_engines(
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=service.list_engines())


@router.get("/providers")
async def list_providers(
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=service.list_providers())


@router.get("/config")
async def get_config(
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[dict[str, object]]:
    return ApiResponse(data=service.get_config())


@router.get("/preflight")
async def preflight(
    scope: str = "all",
    experiment_id: str | None = None,
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(
        data=await service.get_preflight(scope=scope, experiment_id=experiment_id)
    )


@router.post("/seed-demo")
async def seed_demo(
    service: DemoSeedService = Depends(get_demo_seed_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await service.seed_demo())


@router.get("/storage")
async def get_storage(
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[dict[str, Any]]:
    """Return storage usage information."""
    return ApiResponse(data=await service.get_storage_info())


@router.get("/runtime-stats")
async def runtime_stats(
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=service.get_runtime_stats())


@router.get("/benchmark-seeds")
async def benchmark_seeds(
    game_type: str | None = None,
    service: SystemService = Depends(get_system_service),
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=service.get_benchmark_seeds(game_type))


@router.get("/archive/stats")
async def get_archive_stats(
    archive_service: ArchiveService = Depends(get_archive_service),
) -> ApiResponse[dict[str, Any]]:
    """Get statistics about archivable data."""
    return ApiResponse(data=await archive_service.get_archive_stats())


@router.get("/archive/list")
async def list_archives(
    archive_service: ArchiveService = Depends(get_archive_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """List all archive files."""
    return ApiResponse(data=await archive_service.list_archives())


@router.post("/archive", response_model=ApiResponse[ArchiveResult])
async def archive_old_games(
    request: ArchiveRequest,
    archive_service: ArchiveService = Depends(get_archive_service),
) -> ApiResponse[ArchiveResult]:
    """Archive games older than specified days.

    Set dry_run=true to preview without making changes.
    """
    result = await archive_service.archive_old_games(request)
    return ApiResponse(data=result)


@router.delete("/archive/{filename}")
async def delete_archive(
    filename: str,
    archive_service: ArchiveService = Depends(get_archive_service),
) -> ApiResponse[dict[str, str]]:
    """Delete an archive file."""
    deleted = await archive_service.delete_archive(filename)
    if not deleted:
        return ApiResponse(code=1, message="Archive not found", data={})
    return ApiResponse(data={"message": f"Archive {filename} deleted"})


@router.post("/cleanup", response_model=ApiResponse[CleanupResult])
async def cleanup_old_data(
    request: CleanupRequest,
    archive_service: ArchiveService = Depends(get_archive_service),
) -> ApiResponse[CleanupResult]:
    """Permanently delete old data (use with caution).

    Set dry_run=true to preview without making changes.
    This operation cannot be undone.
    """
    result = await archive_service.cleanup_old_data(request)
    return ApiResponse(data=result)
