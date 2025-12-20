"""
qBittorrent integration module.
"""
import asyncio
from typing import Dict, Any, Optional, List
from qbittorrentapi import Client, LoginFailed
from core.errors import IntegrationError
from .base import BaseIntegration


class QBittorrentIntegration(BaseIntegration):
    """Integration for qBittorrent Web API."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client: Optional[Client] = None
    
    @property
    def name(self) -> str:
        return "qBittorrent"
    
    async def connect(self) -> bool:
        """
        Connect to qBittorrent Web UI.
        
        Returns:
            True if connection successful
            
        Raises:
            IntegrationError: If connection fails
        """
        try:
            host = self.config.get("host")
            username = self.config.get("username")
            password = self.config.get("password")
            
            if not all([host, username, password]):
                raise IntegrationError(
                    "qBittorrent configuration incomplete. "
                    "Missing host, username, or password."
                )
            
            self.client = Client(
                host=host,
                username=username,
                password=password
            )
            
            # Test connection by authenticating
            self.client.auth_log_in()
            self._connected = True
            return True
            
        except LoginFailed as e:
            self._connected = False
            raise IntegrationError(f"qBittorrent login failed: {str(e)}")
        except Exception as e:
            self._connected = False
            raise IntegrationError(f"Failed to connect to qBittorrent: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from qBittorrent."""
        if self.client:
            try:
                self.client.auth_log_out()
            except Exception:
                pass  # Ignore errors on disconnect
            finally:
                self.client = None
                self._connected = False
    
    async def health_check(self) -> bool:
        """
        Check if qBittorrent is accessible.
        
        Returns:
            True if qBittorrent is healthy
        """
        if not self.client:
            return False
        
        try:
            # Simple health check - get app version
            self.client.app_version()
            return True
        except Exception:
            return False
    
    # qBittorrent-specific methods
    
    async def get_torrents(self, status_filter: str = "all") -> list:
        """
        Get list of torrents.
        
        Args:
            status_filter: Filter by status (all, downloading, completed, etc.)
            
        Returns:
            List of torrent dictionaries
        """
        if not self.is_connected:
            raise IntegrationError("Not connected to qBittorrent")
        
        try:
            return self.client.torrents_info(status_filter=status_filter)
        except Exception as e:
            raise IntegrationError(f"Failed to get torrents: {str(e)}")
    
    async def add_torrent(self, torrent: str, save_path: str = None) -> Optional[str]:
        """
        Add a torrent to qBittorrent.
        
        Args:
            torrent: Torrent file path or magnet link
            save_path: Optional save path for the torrent
            
        Returns:
            Torrent hash if successful, None otherwise
        """
        if not self.is_connected:
            raise IntegrationError("Not connected to qBittorrent")
        
        try:
            if save_path:
                self.client.torrents_add(
                    urls=torrent,
                    save_path=save_path
                )
            else:
                self.client.torrents_add(urls=torrent)
            
            # Wait a moment for the torrent to be added
            await asyncio.sleep(2)
            
            # Try to get the torrent hash from the magnet link or by matching name
            # For magnet links, we can extract the hash from the link
            if torrent.startswith("magnet:"):
                # Extract hash from magnet link (format: magnet:?xt=urn:btih:HASH)
                try:
                    import urllib.parse
                    # Parse the magnet link
                    parsed = urllib.parse.urlparse(torrent)
                    params = urllib.parse.parse_qs(parsed.query)
                    
                    # Get the xt parameter (info hash)
                    if 'xt' in params:
                        xt_value = params['xt'][0] if isinstance(params['xt'], list) else params['xt']
                        if 'urn:btih:' in xt_value:
                            hash_value = xt_value.split('urn:btih:')[-1].split('&')[0]
                            
                            # qBittorrent uses lowercase hex hashes (40 chars)
                            # If it's base32 (32 chars), convert to hex
                            if len(hash_value) == 32:  # Base32 encoded
                                import base64
                                try:
                                    # Base32 to hex conversion
                                    decoded = base64.b32decode(hash_value.upper())
                                    hash_value = decoded.hex().lower()
                                except Exception:
                                    # If base32 decode fails, try using it as-is
                                    pass
                            
                            # Ensure it's lowercase and 40 chars (hex)
                            if len(hash_value) == 40:
                                return hash_value.lower()
                except Exception as e:
                    print(f"Error extracting hash from magnet link: {e}")
            
            # Fallback: Get the most recently added torrent
            # This works for both magnet links and torrent files
            try:
                torrents = self.client.torrents_info(sort="added_on", reverse=True, limit=1)
                if torrents:
                    torrent_obj = torrents[0]
                    # Handle both dict and object formats
                    if isinstance(torrent_obj, dict):
                        return torrent_obj.get("hash", None)
                    else:
                        return getattr(torrent_obj, "hash", None)
            except Exception as e:
                print(f"Error getting recently added torrent: {e}")
            
            return None
        except Exception as e:
            raise IntegrationError(f"Failed to add torrent: {str(e)}")
    
    async def get_torrent_by_hash(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get torrent information by hash.
        
        Args:
            torrent_hash: Hash of the torrent
            
        Returns:
            Torrent dictionary or None if not found
        """
        if not self.is_connected:
            raise IntegrationError("Not connected to qBittorrent")
        
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if torrents and len(torrents) > 0:
                torrent = torrents[0]
                # Convert to dict if it's an object
                if isinstance(torrent, dict):
                    return torrent
                else:
                    # Convert object to dict
                    return {
                        "hash": getattr(torrent, "hash", torrent_hash),
                        "name": getattr(torrent, "name", "Unknown"),
                        "state": getattr(torrent, "state", "unknown"),
                        "progress": getattr(torrent, "progress", 0.0),
                        "size": getattr(torrent, "size", 0),
                        "downloaded": getattr(torrent, "downloaded", 0),
                        "uploaded": getattr(torrent, "uploaded", 0),
                        "dlspeed": getattr(torrent, "dlspeed", 0),
                        "upspeed": getattr(torrent, "upspeed", 0),
                        "num_seeds": getattr(torrent, "num_seeds", 0),
                        "num_leechs": getattr(torrent, "num_leechs", 0),
                        "added_on": getattr(torrent, "added_on", 0),
                        "completion_on": getattr(torrent, "completion_on", 0),
                        "content_path": getattr(torrent, "content_path", getattr(torrent, "save_path", "")),
                        "save_path": getattr(torrent, "save_path", getattr(torrent, "content_path", "")),
                    }
            return None
        except Exception as e:
            raise IntegrationError(f"Failed to get torrent by hash: {str(e)}")
    
    async def pause_torrent(self, torrent_hash: str) -> bool:
        """
        Pause a torrent.
        
        Args:
            torrent_hash: Hash of the torrent to pause
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            raise IntegrationError("Not connected to qBittorrent")
        
        try:
            self.client.torrents_pause(torrent_hashes=torrent_hash)
            return True
        except Exception as e:
            raise IntegrationError(f"Failed to pause torrent: {str(e)}")
    
    async def resume_torrent(self, torrent_hash: str) -> bool:
        """
        Resume a torrent.
        
        Args:
            torrent_hash: Hash of the torrent to resume
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            raise IntegrationError("Not connected to qBittorrent")
        
        try:
            self.client.torrents_resume(torrent_hashes=torrent_hash)
            return True
        except Exception as e:
            raise IntegrationError(f"Failed to resume torrent: {str(e)}")
    
    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """
        Delete a torrent.
        
        Args:
            torrent_hash: Hash of the torrent to delete
            delete_files: Whether to also delete downloaded files
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            raise IntegrationError("Not connected to qBittorrent")
        
        try:
            self.client.torrents_delete(
                torrent_hashes=torrent_hash,
                delete_files=delete_files
            )
            return True
        except Exception as e:
            raise IntegrationError(f"Failed to delete torrent: {str(e)}")
    
    async def search_torrents(
        self, 
        pattern: str, 
        plugins: str = "all", 
        category: str = "all",
        wait_time: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for torrents using qBittorrent search plugins.
        
        Args:
            pattern: Search pattern/query
            plugins: Search plugin to use (e.g., 'LimeTorrents', 'all')
            category: Category to search in (default: 'all')
            wait_time: Time in seconds to wait for search results (default: 10)
            
        Returns:
            List of search result dictionaries
            
        Raises:
            IntegrationError: If search fails
        """
        if not self.is_connected:
            raise IntegrationError("Not connected to qBittorrent")
        
        try:
            # Start the search job using qBittorrent search API
            # Equivalent to: qbt_client.search.start(pattern='...', plugins='...', category='...')
            search_job = self.client.search.start(
                pattern=pattern,
                plugins=plugins,
                category=category
            )

            # Wait for search to complete (as per example: time.sleep(10))
            await asyncio.sleep(wait_time)
            
            # Get search status (returns SearchStatusesList - a list-like object)
            # Equivalent to: search_job.status()
            status = search_job.status()
            
            # Get search results (returns SearchResultsDictionary with 'results' key)
            # Equivalent to: search_job.results()
            results_obj = search_job.results()
            
            # Force evaluation of the lazy object by accessing it
            # (Some objects are lazy and only evaluate when accessed)
            _ = str(results_obj) if results_obj else None
            
            # Extract the actual results list from SearchResultsDictionary
            # It's a dict-like object with 'results', 'status', and 'total' keys
            results = []
            if results_obj is None:
                results = []
            else:
                # Try multiple ways to access the 'results' key
                # SearchResultsDictionary supports dict-like access
                try:
                    # First try dict-style access (most likely to work)
                    if hasattr(results_obj, '__getitem__'):
                        try:
                            results = results_obj['results']
                        except (KeyError, TypeError):
                            pass
                    
                    # If that didn't work, try as regular dict
                    if not results and isinstance(results_obj, dict):
                        results = results_obj.get('results', [])
                    
                    # If still no results, try as attribute
                    if not results and hasattr(results_obj, 'results'):
                        results_attr = results_obj.results
                        results = results_attr() if callable(results_attr) else results_attr
                    
                    # If it's already a list, use it directly
                    if not results and isinstance(results_obj, list):
                        results = results_obj
                        
                except Exception:
                    # Last resort: try __dict__
                    try:
                        if hasattr(results_obj, '__dict__'):
                            results = results_obj.__dict__.get('results', [])
                    except:
                        results = []
            
            # Ensure results is a list
            if not isinstance(results, list):
                results = list(results) if hasattr(results, '__iter__') else []
            
            # Extract total from results_obj if available (before limiting)
            total_results = len(results)  # Default to length of results
            if results_obj:
                if isinstance(results_obj, dict):
                    total_results = results_obj.get('total', len(results))
                elif hasattr(results_obj, 'total'):
                    total = results_obj.total
                    total_results = total() if callable(total) else total
            
            # Limit results to 10
            results = results[:10]
            
            # Convert status to a list if it's iterable
            status_list = []
            if status:
                try:
                    # SearchStatusesList is iterable, convert to list
                    status_list = list(status)
                except (TypeError, AttributeError):
                    # If conversion fails, try to access as dict
                    if isinstance(status, dict):
                        status_list = [status]
                    else:
                        status_list = []
            
            return {
                "status": {
                    "total": total_results,
                    "statuses": status_list
                },
                "results": results
            }
        except Exception as e:
            raise IntegrationError(f"Failed to search torrents: {str(e)}")

