"""
Database Service - MariaDB Cloud storage for customers, clusters, and nodes
"""

import mariadb
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from src.ai.config import AIConfig


@dataclass
class Customer:
    id: Optional[int] = None
    name: str = ""
    email: str = ""
    created_at: Optional[datetime] = None


@dataclass
class Cluster:
    id: Optional[int] = None
    customer_id: int = 0
    name: str = ""
    topology: str = "galera"
    environment: str = "production"
    created_at: Optional[datetime] = None


@dataclass
class Node:
    id: Optional[int] = None
    cluster_id: int = 0
    hostname: str = ""
    role: str = "primary"
    cpu_cores: int = 0
    ram_gb: int = 0
    disk_total_gb: int = 0
    storage_type: str = "ssd"
    global_status: Optional[str] = None  # JSON string
    global_variables: Optional[str] = None  # JSON string
    maxscale_config: Optional[str] = None  # JSON string
    created_at: Optional[datetime] = None


class DatabaseService:
    """Service for managing customers, clusters, and nodes in MariaDB Cloud"""
    
    def __init__(self, config: AIConfig):
        self.config = config.skysql
        self._conn = None
    
    def _get_connection(self):
        """Get database connection"""
        if self._conn is None or not self._conn.open:
            self._conn = mariadb.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.username,
                password=self.config.password,
                database=self.config.database,
                ssl=self.config.ssl
            )
        return self._conn
    
    def init_schema(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Customers table - PK: name + email
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_customer (name, email)
            )
        """)
        
        # Clusters table - PK: customer_id + name
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clusters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                topology VARCHAR(50) DEFAULT 'galera',
                environment VARCHAR(50) DEFAULT 'production',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                UNIQUE KEY uk_cluster (customer_id, name)
            )
        """)
        
        # Nodes table - PK: cluster_id + hostname
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cluster_id INT NOT NULL,
                hostname VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'primary',
                cpu_cores INT DEFAULT 0,
                ram_gb INT DEFAULT 0,
                disk_total_gb INT DEFAULT 0,
                storage_type VARCHAR(50) DEFAULT 'ssd',
                global_status JSON,
                global_variables JSON,
                maxscale_config JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE CASCADE,
                UNIQUE KEY uk_node (cluster_id, hostname)
            )
        """)
        
        conn.commit()
        cursor.close()
        return {"status": "success", "message": "Schema initialized"}
    
    # ==================== CUSTOMERS ====================
    
    def create_customer(self, name: str, email: str) -> Dict[str, Any]:
        """Create a new customer (validates uniqueness by name+email)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO customers (name, email) VALUES (?, ?)",
                (name, email)
            )
            conn.commit()
            customer_id = cursor.lastrowid
            return {"success": True, "id": customer_id, "name": name, "email": email}
        except mariadb.IntegrityError:
            return {"success": False, "error": f"Customer with name '{name}' and email '{email}' already exists"}
        finally:
            cursor.close()
    
    def get_customers(self) -> List[Dict[str, Any]]:
        """Get all customers with their cluster counts"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT c.*, 
                   COUNT(DISTINCT cl.id) as cluster_count,
                   COUNT(DISTINCT n.id) as node_count
            FROM customers c
            LEFT JOIN clusters cl ON c.id = cl.customer_id
            LEFT JOIN nodes n ON cl.id = n.cluster_id
            GROUP BY c.id
            ORDER BY c.name
        """)
        
        customers = cursor.fetchall()
        cursor.close()
        return customers
    
    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """Get a single customer by ID"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        customer = cursor.fetchone()
        cursor.close()
        return customer
    
    def delete_customer(self, customer_id: int) -> Dict[str, Any]:
        """Delete a customer (cascades to clusters and nodes)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        
        return {"success": affected > 0, "deleted": affected}
    
    # ==================== CLUSTERS ====================
    
    def create_cluster(self, customer_id: int, name: str, topology: str = "galera", 
                       environment: str = "production") -> Dict[str, Any]:
        """Create a new cluster (validates uniqueness by customer_id+name)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO clusters (customer_id, name, topology, environment) VALUES (?, ?, ?, ?)",
                (customer_id, name, topology, environment)
            )
            conn.commit()
            cluster_id = cursor.lastrowid
            return {"success": True, "id": cluster_id, "customer_id": customer_id, "name": name}
        except mariadb.IntegrityError:
            return {"success": False, "error": f"Cluster '{name}' already exists for this customer"}
        finally:
            cursor.close()
    
    def get_clusters(self, customer_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get clusters, optionally filtered by customer"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if customer_id:
            cursor.execute("""
                SELECT cl.*, c.name as customer_name, c.email as customer_email,
                       COUNT(n.id) as node_count
                FROM clusters cl
                JOIN customers c ON cl.customer_id = c.id
                LEFT JOIN nodes n ON cl.id = n.cluster_id
                WHERE cl.customer_id = ?
                GROUP BY cl.id
                ORDER BY cl.name
            """, (customer_id,))
        else:
            cursor.execute("""
                SELECT cl.*, c.name as customer_name, c.email as customer_email,
                       COUNT(n.id) as node_count
                FROM clusters cl
                JOIN customers c ON cl.customer_id = c.id
                LEFT JOIN nodes n ON cl.id = n.cluster_id
                GROUP BY cl.id
                ORDER BY c.name, cl.name
            """)
        
        clusters = cursor.fetchall()
        cursor.close()
        return clusters
    
    def get_cluster(self, cluster_id: int) -> Optional[Dict[str, Any]]:
        """Get a single cluster by ID"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT cl.*, c.name as customer_name
            FROM clusters cl
            JOIN customers c ON cl.customer_id = c.id
            WHERE cl.id = ?
        """, (cluster_id,))
        cluster = cursor.fetchone()
        cursor.close()
        return cluster
    
    def delete_cluster(self, cluster_id: int) -> Dict[str, Any]:
        """Delete a cluster (cascades to nodes)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM clusters WHERE id = ?", (cluster_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        
        return {"success": affected > 0, "deleted": affected}
    
    # ==================== NODES ====================
    
    def create_node(self, cluster_id: int, hostname: str, role: str = "primary",
                    cpu_cores: int = 0, ram_gb: int = 0, disk_total_gb: int = 0,
                    storage_type: str = "ssd", global_status: Optional[str] = None,
                    global_variables: Optional[str] = None, 
                    maxscale_config: Optional[str] = None) -> Dict[str, Any]:
        """Create a new node (validates uniqueness by cluster_id+hostname)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO nodes (cluster_id, hostname, role, cpu_cores, ram_gb, 
                                   disk_total_gb, storage_type, global_status, 
                                   global_variables, maxscale_config) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cluster_id, hostname, role, cpu_cores, ram_gb, disk_total_gb,
                  storage_type, global_status, global_variables, maxscale_config))
            conn.commit()
            node_id = cursor.lastrowid
            return {"success": True, "id": node_id, "cluster_id": cluster_id, "hostname": hostname}
        except mariadb.IntegrityError:
            return {"success": False, "error": f"Node '{hostname}' already exists in this cluster"}
        finally:
            cursor.close()
    
    def get_nodes(self, cluster_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get nodes, optionally filtered by cluster"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if cluster_id:
            cursor.execute("""
                SELECT n.*, cl.name as cluster_name, cl.topology, c.name as customer_name
                FROM nodes n
                JOIN clusters cl ON n.cluster_id = cl.id
                JOIN customers c ON cl.customer_id = c.id
                WHERE n.cluster_id = ?
                ORDER BY n.hostname
            """, (cluster_id,))
        else:
            cursor.execute("""
                SELECT n.*, cl.name as cluster_name, cl.topology, c.name as customer_name
                FROM nodes n
                JOIN clusters cl ON n.cluster_id = cl.id
                JOIN customers c ON cl.customer_id = c.id
                ORDER BY c.name, cl.name, n.hostname
            """)
        
        nodes = cursor.fetchall()
        cursor.close()
        return nodes
    
    def get_node(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Get a single node by ID with full details"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT n.*, cl.name as cluster_name, cl.topology, c.name as customer_name
            FROM nodes n
            JOIN clusters cl ON n.cluster_id = cl.id
            JOIN customers c ON cl.customer_id = c.id
            WHERE n.id = ?
        """, (node_id,))
        node = cursor.fetchone()
        cursor.close()
        return node
    
    def delete_node(self, node_id: int) -> Dict[str, Any]:
        """Delete a node"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        
        return {"success": affected > 0, "deleted": affected}
    
    # ==================== STATS ====================
    
    def get_stats(self) -> Dict[str, int]:
        """Get overall statistics"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM customers) as customers,
                (SELECT COUNT(*) FROM clusters) as clusters,
                (SELECT COUNT(*) FROM nodes) as nodes
        """)
        
        stats = cursor.fetchone()
        cursor.close()
        return stats
    
    def close(self):
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None
