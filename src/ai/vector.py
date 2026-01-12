"""
Vector Store - MariaDB Cloud Vector Operations

Uses MariaDB's native VECTOR type and vector search capabilities
for storing and retrieving document embeddings.
"""

import json
import mariadb
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import google.generativeai as genai

from .config import AIConfig, SkyQLConfig


@dataclass
class DocumentChunk:
    """A chunk of documentation with its embedding"""
    id: Optional[int]
    source: str  # e.g., "mariadb-docs", "maxscale-docs", "galera-docs"
    title: str
    content: str
    url: Optional[str]
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "content": self.content,
            "url": self.url
        }


class VectorStore:
    """
    MariaDB Cloud Vector Store for RAG
    
    Uses VECTOR type for embeddings and VEC_DISTANCE for similarity search.
    """
    
    EMBEDDING_DIM = 768  # Google's embedding dimension
    
    def __init__(self, config: AIConfig):
        self.config = config
        self.skysql_config = config.skysql
        self._connection = None
        
        # Initialize Gemini for embeddings
        genai.configure(api_key=config.gemini.api_key)
        self.embedding_model = "models/embedding-001"
    
    def _get_connection(self) -> mariadb.Connection:
        """Get or create database connection"""
        if self._connection is None or not self._connection.open:
            self._connection = mariadb.connect(
                host=self.skysql_config.host,
                port=self.skysql_config.port,
                user=self.skysql_config.username,
                password=self.skysql_config.password,
                database=self.skysql_config.database,
                ssl=self.skysql_config.ssl
            )
        return self._connection
    
    def close(self):
        """Close database connection"""
        if self._connection and self._connection.open:
            self._connection.close()
            self._connection = None
    
    def init_schema(self):
        """Initialize the vector store schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.skysql_config.database}")
        cursor.execute(f"USE {self.skysql_config.database}")
        
        # Create documents table with VECTOR type
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doc_embeddings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source VARCHAR(100) NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT NOT NULL,
                url VARCHAR(1000),
                embedding VECTOR(768) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_source (source),
                VECTOR INDEX idx_embedding (embedding)
            ) ENGINE=InnoDB
        """)
        
        # Create error codes table for quick lookup
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                error_code VARCHAR(50) NOT NULL UNIQUE,
                component VARCHAR(50) NOT NULL,
                severity VARCHAR(20),
                message TEXT NOT NULL,
                explanation TEXT,
                solution TEXT,
                embedding VECTOR(768),
                INDEX idx_error_code (error_code),
                INDEX idx_component (component)
            ) ENGINE=InnoDB
        """)
        
        # Create analysis cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                id INT AUTO_INCREMENT PRIMARY KEY,
                input_hash VARCHAR(64) NOT NULL UNIQUE,
                analysis_type VARCHAR(50) NOT NULL,
                result JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_hash (input_hash)
            ) ENGINE=InnoDB
        """)
        
        conn.commit()
        cursor.close()
        
        print("✅ Vector store schema initialized")
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Gemini"""
        result = genai.embed_content(
            model=self.embedding_model,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    
    def get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for query (slightly different task type)"""
        result = genai.embed_content(
            model=self.embedding_model,
            content=query,
            task_type="retrieval_query"
        )
        return result['embedding']
    
    def add_document(self, doc: DocumentChunk) -> int:
        """Add a document chunk to the vector store"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Generate embedding if not provided
        if doc.embedding is None:
            doc.embedding = self.get_embedding(f"{doc.title}\n\n{doc.content}")
        
        # Convert embedding to vector string format
        embedding_str = f"[{','.join(str(x) for x in doc.embedding)}]"
        
        cursor.execute("""
            INSERT INTO doc_embeddings (source, title, content, url, embedding)
            VALUES (?, ?, ?, ?, VEC_FromText(?))
        """, (doc.source, doc.title, doc.content, doc.url, embedding_str))
        
        conn.commit()
        doc_id = cursor.lastrowid
        cursor.close()
        
        return doc_id
    
    def add_documents_batch(self, docs: List[DocumentChunk]) -> List[int]:
        """Add multiple documents efficiently"""
        ids = []
        for doc in docs:
            doc_id = self.add_document(doc)
            ids.append(doc_id)
        return ids
    
    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        source_filter: Optional[str] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for similar documents using vector similarity
        
        Returns list of (document, similarity_score) tuples
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Generate query embedding
        query_embedding = self.get_query_embedding(query)
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        # Build query with optional source filter
        if source_filter:
            cursor.execute("""
                SELECT id, source, title, content, url,
                       VEC_DISTANCE(embedding, VEC_FromText(?)) as distance
                FROM doc_embeddings
                WHERE source = ?
                ORDER BY distance ASC
                LIMIT ?
            """, (embedding_str, source_filter, top_k))
        else:
            cursor.execute("""
                SELECT id, source, title, content, url,
                       VEC_DISTANCE(embedding, VEC_FromText(?)) as distance
                FROM doc_embeddings
                ORDER BY distance ASC
                LIMIT ?
            """, (embedding_str, top_k))
        
        results = []
        for row in cursor.fetchall():
            doc = DocumentChunk(
                id=row[0],
                source=row[1],
                title=row[2],
                content=row[3],
                url=row[4]
            )
            # Convert distance to similarity (1 - normalized_distance)
            similarity = 1.0 / (1.0 + row[5])
            results.append((doc, similarity))
        
        cursor.close()
        return results
    
    def add_error_code(
        self,
        error_code: str,
        component: str,
        message: str,
        severity: Optional[str] = None,
        explanation: Optional[str] = None,
        solution: Optional[str] = None
    ) -> int:
        """Add an error code to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Generate embedding for the error info
        embed_text = f"{error_code} {component}: {message}"
        if explanation:
            embed_text += f"\n{explanation}"
        if solution:
            embed_text += f"\nSolution: {solution}"
        
        embedding = self.get_embedding(embed_text)
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        cursor.execute("""
            INSERT INTO error_codes 
            (error_code, component, severity, message, explanation, solution, embedding)
            VALUES (?, ?, ?, ?, ?, ?, VEC_FromText(?))
            ON DUPLICATE KEY UPDATE
                severity = VALUES(severity),
                message = VALUES(message),
                explanation = VALUES(explanation),
                solution = VALUES(solution),
                embedding = VALUES(embedding)
        """, (error_code, component, severity, message, explanation, solution, embedding_str))
        
        conn.commit()
        error_id = cursor.lastrowid
        cursor.close()
        
        return error_id
    
    def lookup_error(self, error_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Look up similar error codes"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query_embedding = self.get_query_embedding(error_text)
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        cursor.execute("""
            SELECT error_code, component, severity, message, explanation, solution,
                   VEC_DISTANCE(embedding, VEC_FromText(?)) as distance
            FROM error_codes
            ORDER BY distance ASC
            LIMIT ?
        """, (embedding_str, top_k))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "error_code": row[0],
                "component": row[1],
                "severity": row[2],
                "message": row[3],
                "explanation": row[4],
                "solution": row[5],
                "similarity": 1.0 / (1.0 + row[6])
            })
        
        cursor.close()
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM doc_embeddings")
        doc_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT source, COUNT(*) FROM doc_embeddings GROUP BY source")
        source_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("SELECT COUNT(*) FROM error_codes")
        error_count = cursor.fetchone()[0]
        
        cursor.close()
        
        return {
            "total_documents": doc_count,
            "documents_by_source": source_counts,
            "total_error_codes": error_count
        }
