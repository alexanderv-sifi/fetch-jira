"""Configuration management for CAKE."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class CakeConfig:
    """Configuration container for CAKE."""
    
    # API Credentials
    jira_base_url: str
    jira_username: str 
    jira_api_token: str
    confluence_base_url: str
    google_cloud_project: Optional[str] = None
    google_api_key: Optional[str] = None
    
    # Performance Settings
    max_concurrent_calls: int = 5
    api_call_delay: float = 0.1
    request_timeout: int = 30
    
    # Output Settings
    include_permissions: bool = True
    simplified_output: bool = False
    
    @classmethod
    def from_env(cls, env_file: str = ".env") -> "CakeConfig":
        """Load configuration from environment variables."""
        # Determine script directory for .env file
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dotenv_path = os.path.join(script_dir, env_file)
        
        # Load environment variables
        load_dotenv(dotenv_path=dotenv_path, override=True)
        
        # Validate required variables
        required_vars = [
            "JIRA_BASE_URL", "JIRA_USERNAME", "JIRA_API_TOKEN", "CONFLUENCE_BASE_URL"
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        return cls(
            jira_base_url=os.getenv("JIRA_BASE_URL"),
            jira_username=os.getenv("JIRA_USERNAME"),
            jira_api_token=os.getenv("JIRA_API_TOKEN"),
            confluence_base_url=os.getenv("CONFLUENCE_BASE_URL"),
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    
    def __post_init__(self):
        """Normalize URLs after initialization."""
        self.jira_base_url = self.jira_base_url.rstrip('/')
        self.confluence_base_url = self.confluence_base_url.rstrip('/')