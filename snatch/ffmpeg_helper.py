import os
import shutil
import logging
from pathlib import Path
import subprocess
import sys
import asyncio
from typing import Optional, Dict, Any, List, Tuple
import tempfile
import json

# Re-export audio classes from the main implementation
from .audio_processor import EnhancedAudioProcessor, StandaloneAudioProcessor, AudioStats

def locate_ffmpeg() -> Optional[str]:
    """Locate FFmpeg executable with fallback to auto-install"""
    # First check system PATH
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
        
    # Check common Windows locations
    common_paths = [
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        str(Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe"),
    ]
    
    for path in common_paths:
        if os.path.isfile(path):
            return path
            
    # If not found, try to install it
    try:
        logging.info("FFmpeg not found. Attempting to install...")
        setup_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                  "setupfiles", "setup_ffmpeg.py")
        if os.path.exists(setup_script):
            subprocess.run([sys.executable, setup_script], check=True)
            # Check if installation was successful
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                return ffmpeg_path
    except Exception as e:
        logging.error(f"Failed to install FFmpeg: {e}")
    
    return None

def get_ffmpeg_version(ffmpeg_path: str) -> Optional[str]:
    """Get FFmpeg version information"""
    try:
        result = subprocess.run([ffmpeg_path, "-version"], 
                              capture_output=True, text=True, check=True)
        return result.stdout.split('\n')[0]
    except Exception:
        return None

def validate_ffmpeg_installation() -> bool:
    """Validate FFmpeg installation and capabilities"""
    ffmpeg_path = locate_ffmpeg()
    if not ffmpeg_path:
        logging.error("FFmpeg not found and installation failed")
        return False
        
    version = get_ffmpeg_version(ffmpeg_path)
    if not version:
        logging.error("Could not verify FFmpeg version")
        return False
        
    logging.info(f"Found FFmpeg: {version}")
    return True

class VideoUpscaler:
    """Advanced video upscaling with AI enhancement support"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ffmpeg_path = locate_ffmpeg()
        self.temp_dir = Path(tempfile.gettempdir()) / "snatch_upscaling"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Check for Real-ESRGAN availability
        self.realesrgan_available = self._check_realesrgan()
        
    def _check_realesrgan(self) -> bool:
        """Check if Real-ESRGAN is available"""
        try:
            result = subprocess.run(
                ["realesrgan-ncnn-vulkan", "--help"], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logging.warning("Real-ESRGAN not found, will use traditional upscaling")
            return False
    
    async def upscale_video(self, input_path: str, output_path: str, 
                           upscale_config: Dict[str, Any]) -> bool:
        """
        Upscale video using specified method
        
        Args:
            input_path: Path to input video file
            output_path: Path for output upscaled video
            upscale_config: Upscaling configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            method = upscale_config.get("method", "lanczos")
            scale_factor = upscale_config.get("scale_factor", 2)
            
            logging.info(f"Starting video upscaling: {method} {scale_factor}x")
            
            if method == "realesrgan" and self.realesrgan_available:
                return await self._upscale_with_realesrgan(input_path, output_path, upscale_config)
            elif method in ["bicubic", "lanczos"]:
                return await self._upscale_with_ffmpeg(input_path, output_path, upscale_config)
            else:
                logging.warning(f"Unsupported upscaling method: {method}, falling back to lanczos")
                upscale_config["method"] = "lanczos"
                return await self._upscale_with_ffmpeg(input_path, output_path, upscale_config)
                
        except Exception as e:
            logging.error(f"Video upscaling failed: {str(e)}")
            return False
    
    async def _upscale_with_realesrgan(self, input_path: str, output_path: str, 
                                     config: Dict[str, Any]) -> bool:
        """Upscale video using Real-ESRGAN AI upscaling"""
        try:
            scale_factor = config.get("scale_factor", 2)
            model_name = f"RealESRGAN_x{scale_factor}plus"
            
            # Extract frames from video
            frames_dir = self.temp_dir / f"frames_{Path(input_path).stem}"
            frames_dir.mkdir(exist_ok=True)
            
            # Extract frames using FFmpeg
            extract_cmd = [
                self.ffmpeg_path,
                "-i", input_path,
                "-vf", "fps=30",  # Limit to 30fps for processing
                str(frames_dir / "frame_%06d.png")
            ]
            
            logging.info("Extracting video frames...")            
            result = await asyncio.create_subprocess_exec(
                *extract_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, _ = await result.communicate()
            
            if result.returncode != 0:
                logging.error("Failed to extract video frames")
                return False
            
            # Upscale frames with Real-ESRGAN
            upscaled_dir = self.temp_dir / f"upscaled_{Path(input_path).stem}"
            upscaled_dir.mkdir(exist_ok=True)
            
            realesrgan_cmd = [
                "realesrgan-ncnn-vulkan",
                "-i", str(frames_dir),
                "-o", str(upscaled_dir),
                "-n", model_name,
                "-s", str(scale_factor),
                "-f", "png"
            ]
            
            logging.info(f"Upscaling frames with Real-ESRGAN {model_name}...")            
            result = await asyncio.create_subprocess_exec(
                *realesrgan_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, _ = await result.communicate()
            
            if result.returncode != 0:
                logging.error("Real-ESRGAN upscaling failed, falling back to traditional method")
                return await self._upscale_with_ffmpeg(input_path, output_path, 
                                                     {**config, "method": "lanczos"})
            
            # Reconstruct video from upscaled frames
            return await self._reconstruct_video(input_path, output_path, upscaled_dir)
            
        except Exception as e:
            logging.error(f"Real-ESRGAN upscaling error: {str(e)}")
            return await self._upscale_with_ffmpeg(input_path, output_path, 
                                                 {**config, "method": "lanczos"})
        finally:
            # Cleanup temporary directories
            self._cleanup_temp_dirs([frames_dir, upscaled_dir])
    
    async def _upscale_with_ffmpeg(self, input_path: str, output_path: str, 
                                 config: Dict[str, Any]) -> bool:
        """Upscale video using FFmpeg traditional algorithms"""
        try:
            method = config.get("method", "lanczos")
            scale_factor = config.get("scale_factor", 2)
            
            # Get video information
            video_info = await self._get_video_info(input_path)
            if not video_info:
                return False
            
            original_width = int(video_info.get("width", 1920))
            original_height = int(video_info.get("height", 1080))
            
            new_width = original_width * scale_factor
            new_height = original_height * scale_factor
            
            # Check if upscaling would exceed maximum resolution
            max_res = config.get("max_resolution", "4K")
            if max_res == "4K" and (new_width > 3840 or new_height > 2160):
                logging.warning("Upscaling would exceed 4K, limiting to 4K resolution")
                aspect_ratio = original_width / original_height
                if new_width > 3840:
                    new_width = 3840
                    new_height = int(3840 / aspect_ratio)
                if new_height > 2160:
                    new_height = 2160
                    new_width = int(2160 * aspect_ratio)
            
            # Build FFmpeg command for upscaling
            upscale_filter = f"scale={new_width}:{new_height}:flags={method}"
            
            cmd = [
                self.ffmpeg_path,
                "-i", input_path,
                "-vf", upscale_filter,
                "-c:v", "libx264",
                "-crf", "18",  # High quality
                "-preset", "slow",
                "-c:a", "copy",  # Copy audio without re-encoding
                "-y",  # Overwrite output file
                output_path
            ]
            logging.info(f"Upscaling video with FFmpeg {method} to {new_width}x{new_height}")
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await result.communicate()
            
            if result.returncode == 0:
                logging.info("Video upscaling completed successfully")
                return True
            else:
                logging.error(f"FFmpeg upscaling failed: {stderr.decode()}")
                return False
                
        except Exception as e:
            logging.error(f"FFmpeg upscaling error: {str(e)}")
            return False
    
    async def _get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
        """Get video information using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                info = json.loads(stdout.decode())
                # Find video stream
                for stream in info.get("streams", []):
                    if stream.get("codec_type") == "video":
                        return stream
                        
        except Exception as e:
            logging.error(f"Failed to get video info: {str(e)}")
            
        return None
    
    async def _reconstruct_video(self, original_path: str, output_path: str, 
                               frames_dir: Path) -> bool:
        """Reconstruct video from upscaled frames"""
        try:
            # Get original video's audio and frame rate
            video_info = await self._get_video_info(original_path)
            if not video_info:
                return False
                
            fps = video_info.get("r_frame_rate", "30/1")
            
            cmd = [
                self.ffmpeg_path,
                "-framerate", fps,
                "-i", str(frames_dir / "frame_%06d.png"),
                "-i", original_path,
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "slow",
                "-c:a", "copy",
                "-map", "0:v:0",  # Video from upscaled frames
                "-map", "1:a:0",  # Audio from original
                "-y",
                output_path
            ]
            
            logging.info("Reconstructing video from upscaled frames...")
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            _, stderr = await result.communicate()
            
            if result.returncode == 0:
                logging.info("Video reconstruction completed")
                return True
            else:
                logging.error(f"Video reconstruction failed: {stderr.decode()}")
                return False
                
        except Exception as e:
            logging.error(f"Video reconstruction error: {str(e)}")
            return False
    
    def _cleanup_temp_dirs(self, dirs: List[Path]) -> None:
        """Clean up temporary directories"""
        for dir_path in dirs:
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
            except Exception as e:
                logging.warning(f"Failed to cleanup {dir_path}: {str(e)}")
    
    def get_upscaling_presets(self) -> Dict[str, Any]:
        """Get available upscaling presets"""
        from .defaults import UPSCALING_PRESETS
        return UPSCALING_PRESETS

def create_video_upscaler(config: Dict[str, Any]) -> VideoUpscaler:
    """Factory function to create VideoUpscaler instance"""
    return VideoUpscaler(config)
