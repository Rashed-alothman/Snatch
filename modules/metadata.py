import logging
import os
import datetime
import mutagen
import re
from .common_utils import sanitize_filename
from .defaults import FLAC_EXT, opus_ext, webn_ext
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)

class MetadataExtractor:
    """Extract and validate metadata from downloaded media"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
    def extract_metadata(self, info_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract metadata with null-safety checks"""
        if not info_dict:
            return {}
            
        metadata = {}
        
        # Extract basic fields with safe fallbacks
        safe_get = lambda key, default="": info_dict.get(key, default) or default
        
        metadata.update({
            "title": safe_get("title"),
            "uploader": safe_get("uploader"),
            "upload_date": safe_get("upload_date"),
            "description": safe_get("description"),
            "duration": safe_get("duration", 0),
            "view_count": safe_get("view_count", 0),
            "like_count": safe_get("like_count", 0),
            "resolution": self._get_resolution(info_dict),
            "format": safe_get("format"),
            "ext": safe_get("ext"),
        })
        
        # Extract timestamps if available
        if times := self._extract_timestamps(info_dict):
            metadata["timestamps"] = times
            
        # Clean and validate all values
        return self._sanitize_metadata(metadata)
        
    def _get_resolution(self, info: Dict[str, Any]) -> str:
        """Get video resolution with fallback to format parsing"""
        try:
            height = info.get("height", 0)
            width = info.get("width", 0)
            
            if height and width:
                return f"{width}x{height}"
                
            # Try parsing from format
            if fmt := info.get("format", ""):
                if match := re.search(r"(\d+)x(\d+)", fmt):
                    return f"{match.group(1)}x{match.group(2)}"
                    
            return "unknown"
        except Exception:
            return "unknown"
            
    def _extract_timestamps(self, info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract chapter markers and timestamps"""
        timestamps = []
        
        # Try chapters first
        if chapters := info.get("chapters"):
            if isinstance(chapters, list):
                for chapter in chapters:
                    if isinstance(chapter, dict):
                        start = chapter.get("start_time")
                        if start is not None:
                            timestamps.append({
                                "time": start,
                                "title": chapter.get("title", ""),
                            })
                            
        # Try timestamps in description
        if desc := info.get("description"):
            if isinstance(desc, str):
                # Match common timestamp formats
                matches = re.finditer(
                    r"(?:(?:(\d{1,2}):)?(\d{1,2}):(\d{2}))(?:\s*[:-]\s*(.+))?",
                    desc
                )
                
                for match in matches:
                    try:
                        hours = int(match.group(1)) if match.group(1) else 0
                        mins = int(match.group(2))
                        secs = int(match.group(3))
                        title = match.group(4) or ""
                        
                        time_secs = hours * 3600 + mins * 60 + secs
                        timestamps.append({
                            "time": time_secs,
                            "title": title.strip()
                        })
                    except (ValueError, AttributeError):
                        continue
                        
        return sorted(timestamps, key=lambda x: x["time"])
        
    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate metadata values"""
        cleaned = {}
        
        for key, value in metadata.items():
            # Convert None to appropriate defaults
            if value is None:
                if key in ("duration", "view_count", "like_count"):
                    cleaned[key] = 0
                else:
                    cleaned[key] = ""
                continue
                
            # Sanitize strings
            if isinstance(value, str):
                # Remove control characters and normalize whitespace
                cleaned_str = re.sub(r"[\x00-\x1f\x7f]", "", value)
                cleaned_str = " ".join(cleaned_str.split())
                cleaned[key] = cleaned_str or ""  # Use empty string if fully cleaned
                continue
                
            # Ensure numeric fields are valid
            if key in ("duration", "view_count", "like_count"):
                try:
                    cleaned[key] = int(value)
                except (TypeError, ValueError):
                    cleaned[key] = 0
                continue
                
            # Pass through other types unchanged
            cleaned[key] = value
            
        return cleaned
