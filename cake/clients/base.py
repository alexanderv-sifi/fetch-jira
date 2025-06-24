"""Base client with common functionality."""

import logging
import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from requests.auth import HTTPBasicAuth
import requests


class BaseClient(ABC):
    """Base class for all API clients."""
    
    def __init__(self, base_url: str, username: str, api_token: str, 
                 max_concurrent_calls: int = 5, api_call_delay: float = 0.1,
                 timeout: int = 30):
        """Initialize base client."""
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self.api_call_delay = api_call_delay
        self.timeout = timeout
        
        # Authentication and headers
        self.auth = HTTPBasicAuth(username, api_token)
        self.headers = {"Accept": "application/json"}
        
        # Concurrency control
        self.semaphore = threading.Semaphore(max_concurrent_calls)
        
        logging.debug(f"Initialized {self.__class__.__name__} for {base_url}")
    
    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated API request with error handling."""
        self.semaphore.acquire()
        try:
            time.sleep(self.api_call_delay)
            response = requests.get(
                url, 
                headers=self.headers, 
                auth=self.auth, 
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed for {url}: {e}")
            raise
        finally:
            self.semaphore.release()
    
    def _paginated_request(self, url: str, params: Optional[Dict[str, Any]] = None, 
                          start_param: str = "start", limit_param: str = "limit",
                          limit: int = 100) -> list:
        """Make paginated API requests."""
        all_results = []
        start = 0
        
        if params is None:
            params = {}
        
        while True:
            page_params = {**params, start_param: start, limit_param: limit}
            response_data = self._make_request(url, page_params)
            
            results = response_data.get("results", [])
            if not results:
                break
                
            all_results.extend(results)
            
            # Check if we got fewer results than requested (last page)
            if len(results) < limit:
                break
                
            start += limit
        
        if len(all_results) > limit:
            logging.info(f"Paginated request returned {len(all_results)} total results")
        
        return all_results