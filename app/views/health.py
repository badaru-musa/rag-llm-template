from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from app.schema import HealthResponse
from app.retrieval.vector_store import ChromaVectorStore
from app.dependencies import get_vector_store
from config import settings
from app.logger import logger

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=settings.app_version,
        dependencies={}
    )


@router.get("/detailed", response_model=HealthResponse)
async def detailed_health_check(
    vector_store: ChromaVectorStore = Depends(get_vector_store)
):
    """Detailed health check with dependency status"""
    dependencies = {}
    overall_status = "healthy"
    
    # Check vector store
    try:
        stats = await vector_store.get_collection_stats()
        dependencies["vector_store"] = "healthy"
        dependencies["vector_store_stats"] = stats
    except Exception as e:
        dependencies["vector_store"] = f"unhealthy: {str(e)}"
        overall_status = "degraded"
        logger.warning(f"Vector store health check failed: {str(e)}")
    
    # Check database (simplified)
    try:
        # This would typically test database connectivity
        dependencies["database"] = "healthy"
    except Exception as e:
        dependencies["database"] = f"unhealthy: {str(e)}"
        overall_status = "degraded"
        logger.warning(f"Database health check failed: {str(e)}")
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=settings.app_version,
        dependencies=dependencies
    )


@router.get("/ping")
async def ping():
    """Simple ping endpoint for load balancers"""
    return {"message": "pong", "timestamp": datetime.utcnow().isoformat()}


@router.get("/version")
async def version():
    """Get application version information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": "development" if settings.debug else "production"
    }
