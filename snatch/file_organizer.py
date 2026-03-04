"""File organization and management utilities with enhanced cross-platform support."""
import os
import shutil
import logging
import re
import json
import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set, Union

from .common_utils import sanitize_filename, ensure_dir, get_platform_specific_path

logger = logging.getLogger(__name__)

class FileOrganizer:
    """Handles file organization and management for downloads with improved categorization and metadata handling."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the file organizer with configuration."""
        self.config = config
        
        # Set up output directories with platform-specific paths
        self.video_dir = get_platform_specific_path(config.get('video_output', 'videos'))
        self.audio_dir = get_platform_specific_path(config.get('audio_output', 'audio'))
        self.subtitle_dir = get_platform_specific_path(config.get('subtitle_output', 'subtitles'))
        self.thumbnail_dir = get_platform_specific_path(config.get('thumbnail_output', 'thumbnails'))
        self.document_dir = get_platform_specific_path(config.get('document_output', 'documents'))
        self.misc_dir = get_platform_specific_path(config.get('misc_output', 'misc'))
        
        # Setup organization templates with more options
        self.organization_templates = config.get('organization_templates', {
            "video": "{uploader}/{title}",
            "audio": "{artist}/{album}/{title}",
            "podcast": "Podcasts/{uploader}/{title}",
            "audiobook": "Audiobooks/{uploader}/{title}",
            "movie": "Movies/{title} ({upload_year})",
            "series": "Series/{uploader}/{title}",
            "documentary": "Documentaries/{title} ({upload_year})",
            "music_video": "Music Videos/{artist}/{title}",
            "document": "Documents/{uploader}/{title}",
            "ebook": "Books/{author}/{title}",
            "image": "Images/{uploader}/{title}",
            "subtitle": "Subtitles/{language}/{title}"
        })
        
        # Setup file categories and extensions with more comprehensive categorization
        self.audio_exts = set(['.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus', '.m4a', '.wma', '.ape', '.alac'])
        self.video_exts = set(['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.3gp', '.ts', '.mts', '.mpg', '.mpeg'])
        self.subtitle_exts = set(['.srt', '.vtt', '.ass', '.ssa', '.sub', '.sbv', '.usf', '.idx'])
        self.image_exts = set(['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif', '.svg', '.heic', '.heif'])
        self.document_exts = set(['.pdf', '.txt', '.doc', '.docx', '.epub', '.mobi', '.azw', '.azw3', '.rtf', '.odt', '.md', '.tex'])
        self.archive_exts = set(['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz'])
        
        # Initialize content type detection based on metadata patterns
        self._init_content_detection_patterns()
        
        # Ensure all directories exist
        self._ensure_dirs()
    
    def _init_content_detection_patterns(self) -> None:
        """Initialize patterns for content type detection from metadata."""
        self.podcast_patterns = [
            re.compile(r'podcast', re.IGNORECASE),
            re.compile(r'episode\s+\d+', re.IGNORECASE)
        ]
        
        self.audiobook_patterns = [
            re.compile(r'audiobook', re.IGNORECASE),
            re.compile(r'chapter\s+\d+', re.IGNORECASE)
        ]
        
        self.movie_patterns = [
            re.compile(r'movie', re.IGNORECASE),
            re.compile(r'film', re.IGNORECASE),
            re.compile(r'\(\d{4}\)', re.IGNORECASE)  # Year in parentheses
        ]
        
        self.series_patterns = [
            re.compile(r'(s\d{1,2}e\d{1,2}|season\s+\d+\s+episode\s+\d+)', re.IGNORECASE),
            re.compile(r'series', re.IGNORECASE)
        ]
        
        self.documentary_patterns = [
            re.compile(r'documentary', re.IGNORECASE),
            re.compile(r'docuseries', re.IGNORECASE)
        ]
    
    def _ensure_dirs(self) -> None:
        """Ensure all necessary directories exist."""
        ensure_dir(self.video_dir)
        ensure_dir(self.audio_dir)
        ensure_dir(self.subtitle_dir)
        ensure_dir(self.thumbnail_dir)
        ensure_dir(self.document_dir)
        ensure_dir(self.misc_dir)
        
        # Create content type subdirectories
        for content_type in ["Movies", "Series", "Podcasts", "Audiobooks", "Music Videos", "Documentaries"]:
            if content_type.lower() == "movies" or content_type.lower() == "documentaries":
                ensure_dir(os.path.join(self.video_dir, content_type))
            elif content_type.lower() == "series":
                ensure_dir(os.path.join(self.video_dir, content_type))
            elif content_type.lower() in ["podcasts", "audiobooks"]:
                ensure_dir(os.path.join(self.audio_dir, content_type))
            elif content_type.lower() == "music videos":
                ensure_dir(os.path.join(self.video_dir, content_type))
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename by removing invalid characters."""
        return sanitize_filename(filename)
    
    def _matches_any_pattern(self, text: str, patterns: List[re.Pattern]) -> bool:
        """Check if text matches any of the given patterns."""
        if not text:
            return False
            
        for pattern in patterns:
            if pattern.search(text):
                return True
                
        return False
        
    def _is_high_definition(self, metadata: Dict[str, Any]) -> bool:
        """Check if video is high definition based on metadata."""
        height = metadata.get('height', 0)
        return height >= 720
        
    def _get_audio_quality(self, metadata: Dict[str, Any]) -> str:
        """Determine audio quality from metadata."""
        abr = metadata.get('abr', 0)
        acodec = str(metadata.get('acodec', '')).lower()
        
        if (abr > 320) or ('flac' in acodec) or ('alac' in acodec) or ('pcm' in acodec):
            return 'high'
        elif abr >= 192:
            return 'medium'
        else:
            return 'low'
    
    def detect_content_type(self, filepath: str, metadata: Dict[str, Any] = None) -> str:
        """
        Detect the content type based on file extension, metadata, and naming patterns.
        
        Args:
            filepath: Path to the file
            metadata: Optional metadata dictionary
            
        Returns:
            Content type: detailed content type string
        """
        ext = os.path.splitext(filepath)[1].lower()
        filename = os.path.basename(filepath)
        metadata = metadata or {}
        
        # Check if metadata explicitly provides a content type
        if metadata and 'content_type' in metadata:
            return metadata['content_type']
            
        # Check for subtitles first (as they might have video extensions like .mp4)
        if ext in self.subtitle_exts or (metadata.get('_type') == 'subtitles'):
            return 'subtitle'
            
        # Use extensions to determine basic content type
        if ext in self.audio_exts:
            # Process audio file types
            return self._detect_audio_type(filepath, filename, metadata)
            
        if ext in self.video_exts:
            # Process video file types
            return self._detect_video_type(filepath, filename, metadata)
            
        if ext in self.image_exts:
            return 'image'
            
        if ext in self.document_exts:
            # Check for ebooks
            if metadata.get('author') or ext in ['.epub', '.mobi', '.azw', '.azw3']:
                return 'ebook'
            return 'document'
            
        if ext in self.archive_exts:
            return 'archive'
            
        # Default to misc for unknown types
        return 'misc'
    def _detect_audio_type(self, _: str, filename: str, metadata: Dict[str, Any]) -> str:
        """Detect specific audio content type."""
        title = metadata.get('title', filename)
        description = metadata.get('description', '')
        
        # Check for podcast
        if (metadata.get('genre', '').lower() in ['podcast', 'podcasts'] or
                self._matches_any_pattern(title, self.podcast_patterns) or
                self._matches_any_pattern(description, self.podcast_patterns)):
            return 'podcast'
            
        # Check for audiobook
        if (metadata.get('genre', '').lower() in ['audiobook', 'audiobooks'] or
                self._matches_any_pattern(title, self.audiobook_patterns) or
                self._matches_any_pattern(description, self.audiobook_patterns)):
            return 'audiobook'
            
        # Default to regular audio
        return 'audio'
    
    def _detect_video_type(self, _: str, filename: str, metadata: Dict[str, Any]) -> str:
        """Detect specific video content type."""
        title = metadata.get('title', filename)
        description = metadata.get('description', '')
        
        # Check for series/TV show
        if (metadata.get('season_number') is not None or 
                metadata.get('episode_number') is not None or
                self._matches_any_pattern(title, self.series_patterns) or
                self._matches_any_pattern(description, self.series_patterns)):
            return 'series'
            
        # Check for movie
        duration = metadata.get('duration', 0)
        if (metadata.get('release_year') or 
                (duration and duration > 60*60) or  # Longer than 1 hour
                self._matches_any_pattern(title, self.movie_patterns) or
                self._matches_any_pattern(description, self.movie_patterns)):
            return 'movie'
            
        # Check for documentary
        if (self._matches_any_pattern(title, self.documentary_patterns) or
                self._matches_any_pattern(description, self.documentary_patterns)):
            return 'documentary'
            
        # Check for music video
        if (metadata.get('artist') and duration and duration < 10*60) or metadata.get('track'):
            return 'music_video'
            
        # Default to generic video
        return 'video'
    def _format_path_from_template(self, template: str, metadata: Dict[str, Any], base_filename: str) -> str:
        """Format a path using a template and metadata with improved error handling."""
        # Extract basic metadata with defaults
        path_meta = self._extract_basic_path_metadata(metadata, base_filename)
        
        # Add special metadata fields
        self._add_episode_metadata(path_meta, metadata)
        self._add_date_metadata(path_meta, metadata)
            
        # Add custom fields from metadata
        for key, value in metadata.items():
            if key not in path_meta and isinstance(value, (str, int, float, bool)):
                path_meta[key] = self._sanitize_filename(str(value))
        
        # Format path from template
        try:
            return template.format(**path_meta)
        except KeyError as e:
            logger.warning(f"Missing key in template: {e}, using default")
            # Fallback to a simple template
            return f"{path_meta['uploader']}/{path_meta['title']}"
        except (ValueError, TypeError) as e:
            logger.warning(f"Error formatting path from template: {e}")
            # Safe fallback
            return path_meta['title']
            
    def _extract_basic_path_metadata(self, metadata: Dict[str, Any], base_filename: str) -> Dict[str, Any]:
        """Extract basic metadata needed for path templates."""
        return {
            "title": self._sanitize_filename(metadata.get("title", base_filename)),
            "uploader": self._sanitize_filename(metadata.get("uploader", "Unknown")),
            "artist": self._sanitize_filename(metadata.get("artist", metadata.get("uploader", "Unknown"))),
            "album": self._sanitize_filename(metadata.get("album", "Unknown")),
            "upload_year": metadata.get("upload_date", "")[:4] if metadata.get("upload_date") else "",
            "genre": self._sanitize_filename(metadata.get("genre", "")),
            "author": self._sanitize_filename(metadata.get("author", metadata.get("uploader", "Unknown"))),
            "language": self._sanitize_filename(metadata.get("language", "Unknown")),
            "ext": os.path.splitext(base_filename)[1].lstrip(".").lower()
        }
        
    def _add_episode_metadata(self, path_meta: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Add TV show episode related metadata."""
        if "season_number" in metadata or "episode_number" in metadata:
            season = metadata.get("season_number", 0)
            episode = metadata.get("episode_number", 0)
            path_meta["season"] = f"Season {season:02d}" if season else "Season 01"
            path_meta["episode"] = f"E{episode:02d}" if episode else ""
            if path_meta.get("season") and path_meta.get("episode"):
                path_meta["se"] = f"{path_meta['season']} - {path_meta['episode']}"
                
    def _add_date_metadata(self, path_meta: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Add date-related metadata fields."""
        if "upload_date" in metadata and len(metadata["upload_date"]) >= 8:
            date = metadata["upload_date"]
            path_meta["year"] = date[:4]
            path_meta["month"] = date[4:6]
            path_meta["day"] = date[6:8]
            path_meta["date"] = f"{path_meta['year']}-{path_meta['month']}-{path_meta['day']}"
    
    def organize_file(self, filepath: str, metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Organize a file based on its content type and metadata with enhanced error handling.
        
        Args:
            filepath: Path to the file to organize
            metadata: Optional metadata dictionary
            
        Returns:
            New file path if organization was successful, None otherwise
        """
        if not os.path.exists(filepath):
            logger.error(f"Cannot organize: File not found: {filepath}")
            return None
            
        try:
            # Extract filename and extension
            filename = os.path.basename(filepath)
            base, ext = os.path.splitext(filename)
            
            # Detect content type
            content_type = self.detect_content_type(filepath, metadata)
            
            # Get appropriate template
            template = self.organization_templates.get(content_type, "{title}")
            
            # Extract needed metadata
            meta = metadata or {}
            
            # Format path from template
            rel_path = self._format_path_from_template(template, meta, base)
                
            # Determine base directory
            base_dir = self._get_base_dir_for_content_type(content_type)
                
            # Create full directory path
            dir_path = os.path.join(base_dir, os.path.dirname(rel_path))
            ensure_dir(dir_path)
            
            # Create full target path
            target_filename = f"{os.path.basename(rel_path)}{ext}"
            target_path = os.path.join(dir_path, target_filename)
            
            # Handle file already exists
            target_path = self._handle_duplicate_filename(filepath, target_path)
            
            # Move the file to the new location
            if not os.path.exists(target_path) or not os.path.samefile(filepath, target_path):
                # Create parent directory if it doesn't exist
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                # Move the file
                shutil.move(filepath, target_path)
                logger.info(f"Organized file: {filepath} -> {target_path}")
                
                # Create metadata sidecar file
                if meta and content_type not in ['subtitle', 'image']:
                    self._create_metadata_sidecar(target_path, meta)
            
            return target_path
            
        except Exception as e:
            logger.error(f"Error organizing file {filepath}: {str(e)}")
            return None
    
    def _get_base_dir_for_content_type(self, content_type: str) -> str:
        """Get the base directory for a specific content type."""
        if content_type in ['audio', 'podcast', 'audiobook']:
            return self.audio_dir
        elif content_type in ['video', 'movie', 'series', 'documentary', 'music_video']:
            return self.video_dir
        elif content_type == 'subtitle':
            return self.subtitle_dir
        elif content_type == 'image':
            return self.thumbnail_dir
        elif content_type in ['document', 'ebook']:
            return self.document_dir
        else:
            return self.misc_dir
    def _handle_duplicate_filename(self, source_path: str, target_path: str) -> str:
        """
        Handle duplicate filenames by adding a counter or using the file hash.
        
        Args:
            source_path: Original file path
            target_path: Desired target path that might already exist
            
        Returns:
            Modified target path that doesn't conflict
        """
        if os.path.exists(target_path) and not os.path.samefile(source_path, target_path):
            base_target, ext = os.path.splitext(target_path)
            counter = 1
            
            # Try adding incremental counter
            while os.path.exists(target_path):
                target_path = f"{base_target}_{counter}{ext}"
                counter += 1
                
                # If we've tried too many counters, use hash instead
                if counter > 100:
                    # Generate hash from file content and timestamp
                    try:
                        file_hash = hashlib.md5()
                        with open(source_path, 'rb') as f:
                            file_hash.update(f.read(8192))  # Read first 8KB for hash
                        file_hash.update(str(datetime.now().timestamp()).encode())
                        hash_suffix = file_hash.hexdigest()[:8]
                        target_path = f"{base_target}_{hash_suffix}{ext}"
                        break
                    except Exception as e:
                        logger.warning(f"Failed to generate hash for {source_path}: {e}")
                        # If hash fails, just use high counter
                        target_path = f"{base_target}_{counter}{ext}"
                        break
                        
        return target_path
    
    def _create_metadata_sidecar(self, filepath: str, metadata: Dict[str, Any]) -> None:
        """
        Create a metadata sidecar file.
        
        Args:
            filepath: Path to the main file
            metadata: Metadata to save
        """
        try:
            meta_path = f"{os.path.splitext(filepath)[0]}.info.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to create metadata sidecar: {e}")
    def organize_related_files(self, main_file: str, metadata: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Organize related files (subtitles, thumbnails, etc.) with improved detection.
        
        Args:
            main_file: Path to the main file that related files belong to
            metadata: Optional metadata dictionary
            
        Returns:
            Dictionary of {original_path: organized_path} for all organized files
        """
        if not os.path.exists(main_file):
            logger.error(f"Cannot organize related files: Main file not found: {main_file}")
            return {}
            
        results = {}
        main_dir = os.path.dirname(main_file)
        main_base = os.path.splitext(os.path.basename(main_file))[0]
        
        # Get content type and determine formats for related files
        main_content_type = self.detect_content_type(main_file, metadata)
        is_video = main_content_type in ['video', 'movie', 'series', 'documentary', 'music_video']
        
        # Find potential related files
        for file in os.listdir(main_dir):
            filepath = os.path.join(main_dir, file)
            if os.path.isfile(filepath) and filepath != main_file:
                file_base, file_ext = os.path.splitext(file)
                
                # Check if it's related to the main file
                is_related = (
                    file_base == main_base or 
                    file_base.startswith(f"{main_base}.") or
                    file_base.endswith(f".{main_base}") or
                    f".{main_base}." in file_base
                )
                
                if is_related:
                    # Determine content type of the related file
                    rel_content_type = self.detect_content_type(filepath, metadata)
                    
                    # Determine target directory based on content type and relation
                    if rel_content_type == 'subtitle' and is_video:
                        target_dir = os.path.join(self.subtitle_dir, main_base)
                    elif rel_content_type == 'image':
                        target_dir = os.path.join(self.thumbnail_dir, main_base)
                    elif file_ext.lower() in ['.nfo', '.txt', '.info.json', '.description', '.annotations.xml']:
                        # Info files should stay with the main file
                        continue
                    else:
                        # For other file types, try to organize them by their own content type
                        target_dir = os.path.join(self._get_base_dir_for_content_type(rel_content_type), main_base)
                    
                    ensure_dir(target_dir)
                    target_path = os.path.join(target_dir, file)
                    
                    # Handle file already exists
                    target_path = self._handle_duplicate_filename(filepath, target_path)
                    
                    # Move the file
                    try:
                        if not os.path.exists(target_path) or not os.path.samefile(filepath, target_path):
                            # Create parent directory if it doesn't exist
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            
                            shutil.move(filepath, target_path)
                            results[filepath] = target_path
                    except Exception as e:
                        logger.error(f"Error organizing related file {filepath}: {str(e)}")
        
        return results
    
    def list_files_by_type(self, content_type: str) -> List[str]:
        """
        List all files of a specific content type.
        
        Args:
            content_type: Content type to filter by
            
        Returns:
            List of file paths
        """
        base_dir = self._get_base_dir_for_content_type(content_type)
        result = []
        
        extensions = self._get_extensions_for_content_type(content_type)
        
        for root, _, files in os.walk(base_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in extensions):
                    result.append(os.path.join(root, file))
        
        return result
    def _get_extensions_for_content_type(self, content_type: str) -> Set[str]:
        """Get file extensions for a specific content type."""
        # For audio content types
        if content_type in ['audio', 'podcast', 'audiobook']:
            return self.audio_exts
        # For video content types    
        elif content_type in ['video', 'movie', 'series', 'documentary', 'music_video']:
            return self.video_exts
        # For specific content types
        elif content_type == 'subtitle':
            return self.subtitle_exts
        elif content_type == 'image':
            return self.image_exts
        elif content_type in ['document', 'ebook']:
            return self.document_exts
        # For miscellaneous or unknown content types
        else:
            # Return combined extensions
            all_exts = set()
            all_exts.update(self.audio_exts)
            all_exts.update(self.video_exts)
            all_exts.update(self.subtitle_exts)
            all_exts.update(self.image_exts)
            all_exts.update(self.document_exts)
            all_exts.update(self.archive_exts)
            return all_exts
    def search_files(self, query: str, content_types: Optional[List[str]] = None) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Search for files with metadata matching the query.
        
        Args:
            query: Search query
            content_types: Optional list of content types to search in
            
        Returns:
            List of (file_path, metadata) tuples matching the query
        """
        # Normalize query
        query_lower = query.lower()
        results = []
        
        # Determine content types to search
        if not content_types:
            content_types = ['audio', 'video', 'movie', 'series', 'podcast', 'audiobook', 
                           'documentary', 'music_video', 'document', 'ebook']
        
        # Search each content type
        for content_type in content_types:
            files = self.list_files_by_type(content_type)
            
            for file_path in files:
                # Check filename match
                if query_lower in os.path.basename(file_path).lower():
                    metadata = self._get_file_metadata(file_path)
                    results.append((file_path, metadata))
                    continue
                    
                # Check metadata match if filename didn't match
                metadata = self._get_file_metadata(file_path)
                if metadata:
                    for field in ['title', 'uploader', 'artist', 'album', 'description', 'genre']:
                        if field in metadata and query_lower in str(metadata[field]).lower():
                            results.append((file_path, metadata))
                            break
        
        return results
    def _get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Get metadata for a file from sidecar files.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Metadata dictionary or empty dict if not found
        """
        # Check for .info.json file
        meta_path = f"{os.path.splitext(file_path)[0]}.info.json"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read metadata from {meta_path}: {e}")
                
        # Check for .nfo file (common for media)
        nfo_path = f"{os.path.splitext(file_path)[0]}.nfo"
        if os.path.exists(nfo_path):
            try:
                with open(nfo_path, 'r', encoding='utf-8') as f:
                    return {'description': f.read()}
            except (IOError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read metadata from {nfo_path}: {e}")
                
        return {}
