"""relos/api/v1/health.py — 健康检查端点"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    version: str = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """
    系统健康检查。
    检查 Neo4j 连接是否正常。
    """
    try:
        driver = request.app.state.neo4j_driver
        await driver.verify_connectivity()
        neo4j_status = "ok"
    except Exception:
        neo4j_status = "error"

    return HealthResponse(
        status="ok" if neo4j_status == "ok" else "degraded",
        neo4j=neo4j_status,
    )
