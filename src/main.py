"""
MariaDB Cluster Architecture & Capacity Review Service

A microservice for analyzing MariaDB deployments from standalone nodes
to Galera clusters with MaxScale.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.ai_routes import router as ai_router
from src.api.data_routes import router as data_router

app = FastAPI(
    title="MariaDB Cluster Review Service",
    description="""
    Analyze MariaDB deployments for architecture validation, 
    capacity review, and performance optimization.
    
    ## Supported Topologies
    - Standalone nodes
    - Master-Replica (async replication)
    - Semi-Synchronous replication
    - Galera Cluster (synchronous)
    - MaxScale proxy configurations
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(ai_router)  # AI routes have their own prefix
app.include_router(data_router)  # Data management routes


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "MariaDB Cluster Review Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
