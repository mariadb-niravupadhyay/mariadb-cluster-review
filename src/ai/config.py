"""
AI Configuration - Loads credentials for SkySQL and Gemini
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class SkyQLConfig:
    """MariaDB Cloud connection configuration"""
    host: str
    port: int
    username: str
    password: str
    database: str = "cluster_analyzer"
    ssl: bool = True


@dataclass
class GeminiConfig:
    """Google Gemini API configuration"""
    api_key: str
    model: str = "models/gemini-2.0-flash"  # Latest flash model


@dataclass
class AIConfig:
    """Combined AI configuration"""
    skysql: SkyQLConfig
    gemini: GeminiConfig
    
    @classmethod
    def from_files(cls, base_path: Optional[str] = None) -> "AIConfig":
        """Load configuration from credential files
        
        Config file selection (in order of priority):
        1. If USE_DOCKER_DB=true env var is set, use .skysql_docker
        2. If .skysql_docker exists and .skysql doesn't, use .skysql_docker
        3. Otherwise use .skysql (MariaDB Cloud)
        """
        if base_path is None:
            # Find project root (where .gak and .skysql are located)
            base_path = Path(__file__).parent.parent.parent
        else:
            base_path = Path(base_path)
        
        # Load Gemini API key
        gak_path = base_path / ".gak"
        if not gak_path.exists():
            raise FileNotFoundError(f"Gemini API key file not found: {gak_path}")
        
        gemini_api_key = gak_path.read_text().strip()
        
        # Determine which config file to use
        use_docker = os.environ.get("USE_DOCKER_DB", "").lower() == "true"
        skysql_docker_path = base_path / ".skysql_docker"
        skysql_cloud_path = base_path / ".skysql"
        
        if use_docker and skysql_docker_path.exists():
            skysql_path = skysql_docker_path
            print("[Config] Using Docker MariaDB configuration (.skysql_docker)")
        elif skysql_cloud_path.exists():
            skysql_path = skysql_cloud_path
            print("[Config] Using MariaDB Cloud configuration (.skysql)")
        elif skysql_docker_path.exists():
            skysql_path = skysql_docker_path
            print("[Config] Using Docker MariaDB configuration (.skysql_docker)")
        else:
            raise FileNotFoundError("No credentials file found. Expected .skysql or .skysql_docker")
        
        skysql_lines = skysql_path.read_text().strip().split("\n")
        
        # Parse config
        # Format:
        # host (line 1)
        # port (line 2)
        # username: value (line 3)
        # password: value (line 4)
        # ssl: true/false (line 5, optional - defaults to true)
        
        host = skysql_lines[0].strip()
        port = int(skysql_lines[1].strip())
        username = skysql_lines[2].split(":", 1)[1].strip()
        password = skysql_lines[3].split(":", 1)[1].strip()
        
        # Optional SSL setting (defaults to True for cloud, can be disabled for local)
        ssl = True
        if len(skysql_lines) > 4:
            ssl_value = skysql_lines[4].split(":", 1)[1].strip().lower()
            ssl = ssl_value == "true"
        
        return cls(
            skysql=SkyQLConfig(
                host=host,
                port=port,
                username=username,
                password=password,
                ssl=ssl
            ),
            gemini=GeminiConfig(
                api_key=gemini_api_key
            )
        )
    
    @classmethod
    def from_env(cls) -> "AIConfig":
        """Load configuration from environment variables"""
        return cls(
            skysql=SkyQLConfig(
                host=os.environ["SKYSQL_HOST"],
                port=int(os.environ.get("SKYSQL_PORT", "4005")),
                username=os.environ["SKYSQL_USERNAME"],
                password=os.environ["SKYSQL_PASSWORD"],
                database=os.environ.get("SKYSQL_DATABASE", "cluster_analyzer")
            ),
            gemini=GeminiConfig(
                api_key=os.environ["GEMINI_API_KEY"],
                model=os.environ.get("GEMINI_MODEL", "gemini-pro")
            )
        )
