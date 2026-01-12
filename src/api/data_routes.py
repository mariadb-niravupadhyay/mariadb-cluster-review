"""
Data Routes - API endpoints for managing customers, clusters, and nodes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json

from src.ai.config import AIConfig
from src.services.database import DatabaseService


router = APIRouter(prefix="/api/v1/data", tags=["Data Management"])

# Global database service instance
_db_service: Optional[DatabaseService] = None


def get_db_service() -> DatabaseService:
    """Get or create database service instance"""
    global _db_service
    if _db_service is None:
        config = AIConfig.from_files()
        _db_service = DatabaseService(config)
    return _db_service


# ==================== Request Models ====================

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)


class ClusterCreate(BaseModel):
    customer_id: int
    name: str = Field(..., min_length=1, max_length=255)
    topology: str = Field(default="galera")
    environment: str = Field(default="production")


class NodeCreate(BaseModel):
    cluster_id: int
    hostname: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="primary")
    cpu_cores: int = Field(default=0, ge=0)
    ram_gb: int = Field(default=0, ge=0)
    disk_total_gb: int = Field(default=0, ge=0)
    storage_type: str = Field(default="ssd")
    global_status: Optional[Dict[str, Any]] = None
    global_variables: Optional[Dict[str, Any]] = None
    maxscale_config: Optional[Dict[str, Any]] = None


# ==================== Schema Endpoints ====================

@router.post("/init")
async def init_database():
    """Initialize database schema"""
    try:
        db = get_db_service()
        result = db.init_schema()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get overall statistics"""
    try:
        db = get_db_service()
        return db.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Customer Endpoints ====================

@router.post("/customers")
async def create_customer(customer: CustomerCreate):
    """Create a new customer"""
    try:
        db = get_db_service()
        result = db.create_customer(customer.name, customer.email)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customers")
async def get_customers():
    """Get all customers"""
    try:
        db = get_db_service()
        customers = db.get_customers()
        return {"success": True, "data": customers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: int):
    """Get a single customer"""
    try:
        db = get_db_service()
        customer = db.get_customer(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return {"success": True, "data": customer}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: int):
    """Delete a customer"""
    try:
        db = get_db_service()
        result = db.delete_customer(customer_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail="Customer not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Cluster Endpoints ====================

@router.post("/clusters")
async def create_cluster(cluster: ClusterCreate):
    """Create a new cluster"""
    try:
        db = get_db_service()
        result = db.create_cluster(
            cluster.customer_id,
            cluster.name,
            cluster.topology,
            cluster.environment
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters")
async def get_clusters(customer_id: Optional[int] = None):
    """Get all clusters, optionally filtered by customer"""
    try:
        db = get_db_service()
        clusters = db.get_clusters(customer_id)
        return {"success": True, "data": clusters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters/{cluster_id}")
async def get_cluster(cluster_id: int):
    """Get a single cluster"""
    try:
        db = get_db_service()
        cluster = db.get_cluster(cluster_id)
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return {"success": True, "data": cluster}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clusters/{cluster_id}")
async def delete_cluster(cluster_id: int):
    """Delete a cluster"""
    try:
        db = get_db_service()
        result = db.delete_cluster(cluster_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail="Cluster not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Node Endpoints ====================

@router.post("/nodes")
async def create_node(node: NodeCreate):
    """Create a new node"""
    try:
        db = get_db_service()
        result = db.create_node(
            node.cluster_id,
            node.hostname,
            node.role,
            node.cpu_cores,
            node.ram_gb,
            node.disk_total_gb,
            node.storage_type,
            json.dumps(node.global_status) if node.global_status else None,
            json.dumps(node.global_variables) if node.global_variables else None,
            json.dumps(node.maxscale_config) if node.maxscale_config else None
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes")
async def get_nodes(cluster_id: Optional[int] = None):
    """Get all nodes, optionally filtered by cluster"""
    try:
        db = get_db_service()
        nodes = db.get_nodes(cluster_id)
        return {"success": True, "data": nodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/{node_id}")
async def get_node(node_id: int):
    """Get a single node"""
    try:
        db = get_db_service()
        node = db.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return {"success": True, "data": node}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: int):
    """Delete a node"""
    try:
        db = get_db_service()
        result = db.delete_node(node_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail="Node not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
