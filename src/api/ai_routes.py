"""
AI Routes - API endpoints for AI-powered analysis
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from src.ai.config import AIConfig
from src.ai.rag import RAGService, seed_sample_docs


router = APIRouter(prefix="/api/v1/ai", tags=["AI Analysis"])

# Global RAG service instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create RAG service instance"""
    global _rag_service
    if _rag_service is None:
        config = AIConfig.from_files()
        _rag_service = RAGService(config)
    return _rag_service


# Request/Response Models

class ClusterAnalysisRequest(BaseModel):
    """Request for cluster analysis"""
    cluster_name: str
    topology_type: str = Field(..., description="galera, semi-sync, or async")
    nodes: List[Dict[str, Any]] = Field(..., description="List of node data")
    maxscale_config: Optional[str] = None
    server_config: Optional[str] = None


class NodeCapacityRequest(BaseModel):
    """Request for node capacity analysis"""
    hostname: str
    global_status: Dict[str, Any]
    global_variables: Dict[str, Any]
    system_resources: Optional[Dict[str, Any]] = None


class LogAnalysisRequest(BaseModel):
    """Request for log analysis"""
    log_type: str = Field(..., description="mariadb, maxscale, or galera")
    log_entries: List[str]


class LogTimelineRequest(BaseModel):
    """Request for log timeline analysis"""
    cluster_name: str
    topology_type: str
    node_logs: Dict[str, Any] = Field(..., description="Dict of node_id -> {hostname, role, mariadb_log, maxscale_log}")


class TopologyCompareRequest(BaseModel):
    """Request for topology comparison"""
    current_topology: str
    cluster_data: Dict[str, Any]


class ChatRequest(BaseModel):
    """Request for chat"""
    question: str
    cluster_context: Optional[Dict[str, Any]] = None
    log_entries: Optional[List[str]] = None
    chat_history: Optional[List[Dict[str, str]]] = None


class AnalysisResponse(BaseModel):
    """Generic analysis response"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


# Endpoints

@router.post("/init", response_model=Dict[str, str])
async def initialize_ai():
    """Initialize AI services (create schema, seed docs)"""
    try:
        rag = get_rag_service()
        rag.init()
        seed_sample_docs(rag)
        return {"status": "initialized", "message": "AI services initialized successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=Dict[str, Any])
async def get_ai_stats():
    """Get AI service statistics"""
    try:
        rag = get_rag_service()
        return rag.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/cluster", response_model=AnalysisResponse)
async def analyze_cluster(request: ClusterAnalysisRequest):
    """
    Analyze cluster architecture and configuration with AI
    
    Uses RAG to provide context-aware recommendations.
    """
    try:
        rag = get_rag_service()
        
        cluster_data = {
            "cluster_name": request.cluster_name,
            "topology_type": request.topology_type,
            "nodes": request.nodes,
            "maxscale_config": request.maxscale_config,
            "server_config": request.server_config
        }
        
        analysis = rag.analyze_cluster_with_rag(cluster_data)
        
        return AnalysisResponse(success=True, data=analysis)
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@router.post("/analyze/workload", response_model=AnalysisResponse)
async def analyze_workload(request: ClusterAnalysisRequest):
    """
    Analyze workload and resource utilization to determine if architecture is right-sized
    """
    try:
        rag = get_rag_service()
        
        cluster_data = {
            "cluster_name": request.cluster_name,
            "topology_type": request.topology_type,
            "nodes": request.nodes
        }
        
        analysis = rag.analyze_workload_sizing(cluster_data)
        
        return AnalysisResponse(success=True, data=analysis)
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@router.post("/analyze/capacity", response_model=AnalysisResponse)
async def analyze_node_capacity(request: NodeCapacityRequest):
    """
    Analyze individual node capacity and sizing
    """
    try:
        rag = get_rag_service()
        
        node_data = {
            "hostname": request.hostname,
            "global_status": request.global_status,
            "global_variables": request.global_variables,
            "system_resources": request.system_resources
        }
        
        analysis = rag.analyze_node_capacity_with_rag(node_data)
        
        return AnalysisResponse(success=True, data=analysis)
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@router.post("/analyze/logs", response_model=AnalysisResponse)
async def analyze_logs(request: LogAnalysisRequest):
    """
    Analyze and interpret log entries
    
    Uses RAG to match errors with known issues and documentation.
    """
    try:
        rag = get_rag_service()
        
        interpretations = rag.interpret_logs_with_rag(
            request.log_entries,
            request.log_type
        )
        
        return AnalysisResponse(success=True, data={"interpretations": interpretations})
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@router.post("/analyze/logs/timeline", response_model=AnalysisResponse)
async def analyze_logs_timeline(request: LogTimelineRequest):
    """
    Analyze logs from multiple nodes and extract timeline of events
    """
    try:
        rag = get_rag_service()
        
        analysis = rag.analyze_logs_timeline(
            request.cluster_name,
            request.topology_type,
            request.node_logs
        )
        
        return AnalysisResponse(success=True, data=analysis)
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@router.post("/compare/topologies", response_model=AnalysisResponse)
async def compare_topologies(request: TopologyCompareRequest):
    """
    Compare current topology with alternatives
    """
    try:
        rag = get_rag_service()
        
        comparison = rag.compare_topologies_with_rag(
            request.current_topology,
            request.cluster_data
        )
        
        return AnalysisResponse(success=True, data=comparison)
    except Exception as e:
        return AnalysisResponse(success=False, data={}, error=str(e))


@router.post("/chat", response_model=Dict[str, Any])
async def chat(request: ChatRequest):
    """
    Chat with AI assistant about cluster issues
    
    Uses RAG to provide documentation-backed answers.
    Supports questions about logs if log_entries provided.
    """
    try:
        rag = get_rag_service()
        
        response = rag.chat_with_rag(
            request.question,
            cluster_context=request.cluster_context,
            log_entries=request.log_entries,
            chat_history=request.chat_history
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/add", response_model=Dict[str, Any])
async def add_document(
    source: str,
    title: str,
    content: str,
    url: Optional[str] = None
):
    """Add a document to the vector store"""
    try:
        rag = get_rag_service()
        from ...ai.vector import DocumentChunk
        
        doc = DocumentChunk(
            id=None,
            source=source,
            title=title,
            content=content,
            url=url
        )
        
        doc_id = rag.vector_store.add_document(doc)
        
        return {"success": True, "document_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/errors/add", response_model=Dict[str, Any])
async def add_error_code(
    error_code: str,
    component: str,
    message: str,
    severity: Optional[str] = None,
    explanation: Optional[str] = None,
    solution: Optional[str] = None
):
    """Add an error code to the knowledge base"""
    try:
        rag = get_rag_service()
        
        error_id = rag.vector_store.add_error_code(
            error_code=error_code,
            component=component,
            message=message,
            severity=severity,
            explanation=explanation,
            solution=solution
        )
        
        return {"success": True, "error_id": error_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_documents(query: str, top_k: int = 5, source: Optional[str] = None):
    """Search the vector store for relevant documents"""
    try:
        rag = get_rag_service()
        
        results = rag.vector_store.search(query, top_k=top_k, source_filter=source)
        
        return [
            {
                "document": doc.to_dict(),
                "similarity": score
            }
            for doc, score in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
