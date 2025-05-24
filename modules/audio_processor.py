"""
Enhanced audio processing with FFmpeg for Snatch.
Handles high-quality 7.1 surround upmix and audio enhancements.

Features:
- Advanced 7.1 channel upmixing using intelligently designed filter chains
- Professional-grade audio denoising with multi-stage processing
- EBU R128 loudness normalization with pyloudnorm
- Audio restoration and enhancement
- Cross-platform compatibility
- Detailed audio analysis and visualization
- Psychoacoustic-based processing with librosa
- AI-enhanced noise reduction with noisereduce
- FLAC validation and integrity checking
"""

import asyncio
import logging
import os
import subprocess
import platform
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
import tempfile
import shutil
import sys

# Enhanced audio processing imports
try:
    import librosa
    import numpy as np
    import soundfile as sf
    import scipy.signal
    import noisereduce as nr
    import pyloudnorm as pyln
    ENHANCED_PROCESSING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Enhanced audio processing libraries not available: {e}")
    ENHANCED_PROCESSING_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Constants
FLAC_EXT = '.flac'

class AudioProcessingError(Exception):
    """Base exception for audio processing errors"""
    pass

class StandaloneAudioProcessor:
    """Standalone audio processor that works without downloading files first"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.supported_formats = ['.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.opus']
        
    def process_local_file(self, input_path: str, output_path: str = None, 
                          normalize: bool = True, denoise: bool = True, 
                          upmix_surround: bool = False, target_channels: int = 8) -> bool:
        """Process a local audio file with all enhancements"""
        try:
            if not os.path.exists(input_path):
                logger.error(f"Input file not found: {input_path}")
                return False
                
            if not output_path:
                base, ext = os.path.splitext(input_path)
                output_path = f"{base}_enhanced{ext}"
            
            # Create temporary processing directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = os.path.join(temp_dir, "temp_audio.wav")
                
                # Convert to WAV for processing
                if not self._convert_to_wav(input_path, temp_file):
                    return False
                
                # Apply processing chain
                processed_file = temp_file
                
                if denoise and ENHANCED_PROCESSING_AVAILABLE:
                    denoised_file = os.path.join(temp_dir, "denoised.wav")
                    if self._apply_noise_reduction(processed_file, denoised_file):
                        processed_file = denoised_file
                
                if normalize:
                    normalized_file = os.path.join(temp_dir, "normalized.wav")
                    if self._apply_normalization(processed_file, normalized_file):
                        processed_file = normalized_file
                
                if upmix_surround:
                    upmixed_file = os.path.join(temp_dir, "upmixed.wav")
                    if self._apply_surround_upmix(processed_file, upmixed_file, target_channels):
                        processed_file = upmixed_file
                
                # Convert to final format
                return self._convert_final_format(processed_file, output_path)
                
        except Exception as e:
            logger.error(f"Error processing audio file: {e}")
            return False
    
    def _convert_to_wav(self, input_path: str, output_path: str) -> bool:
        """Convert audio file to WAV format for processing"""
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-acodec', 'pcm_s24le',
                '-ar', '48000',
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error converting to WAV: {e}")
            return False
    
    def _apply_noise_reduction(self, input_path: str, output_path: str) -> bool:
        """Apply AI-powered noise reduction"""
        try:
            if not ENHANCED_PROCESSING_AVAILABLE:
                return False
                
            # Load audio
            data, rate = librosa.load(input_path, sr=None)
            
            # Apply noise reduction
            reduced_noise = nr.reduce_noise(y=data, sr=rate, stationary=False, prop_decrease=0.8)
            
            # Save processed audio
            sf.write(output_path, reduced_noise, rate)
            return True
            
        except Exception as e:
            logger.error(f"Error applying noise reduction: {e}")
            return False
    
    def _apply_normalization(self, input_path: str, output_path: str) -> bool:
        """Apply professional loudness normalization"""
        try:
            if not ENHANCED_PROCESSING_AVAILABLE:
                # Fallback to FFmpeg normalization
                cmd = [
                    'ffmpeg', '-i', input_path,
                    '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
                    '-y', output_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0
            
            # Use pyloudnorm for professional normalization
            data, rate = librosa.load(input_path, sr=None)
            
            # Measure loudness
            meter = pyln.Meter(rate)
            loudness = meter.integrated_loudness(data)
            
            # Normalize to -16 LUFS
            normalized_audio = pyln.normalize.loudness(data, loudness, -16.0)
            
            # Save normalized audio
            sf.write(output_path, normalized_audio, rate)
            return True
            
        except Exception as e:
            logger.error(f"Error applying normalization: {e}")
            return False
    
    def _apply_surround_upmix(self, input_path: str, output_path: str, target_channels: int = 8) -> bool:
        """Apply advanced 7.1 surround sound upmixing"""
        try:
            # Advanced 7.1 surround upmix filter chain
            if target_channels == 8:  # 7.1 surround
                filter_complex = (
                    # Split input into multiple channels
                    "[0:a]channelsplit=channel_layout=stereo[FL][FR];"
                    # Create center channel (dialogue enhancement)
                    "[FL][FR]amix=inputs=2:weights=0.5 0.5,highpass=f=200,lowpass=f=8000[C];"
                    # Create LFE channel (bass extraction)
                    "[FL][FR]amix=inputs=2:weights=0.5 0.5,lowpass=f=120[LFE];"
                    # Create side channels (ambient expansion)
                    "[FL]adelay=10,highpass=f=300,lowpass=f=10000[SL];"
                    "[FR]adelay=10,highpass=f=300,lowpass=f=10000[SR];"
                    # Create rear channels (spacial depth)
                    "[FL]adelay=20,highpass=f=400,lowpass=f=8000,volume=0.7[RL];"
                    "[FR]adelay=20,highpass=f=400,lowpass=f=8000,volume=0.7[RR];"
                    # Mix all channels together
                    "[FL][FR][C][LFE][RL][RR][SL][SR]amerge=inputs=8[out]"
                )
            elif target_channels == 6:  # 5.1 surround
                filter_complex = (
                    "[0:a]channelsplit=channel_layout=stereo[FL][FR];"
                    "[FL][FR]amix=inputs=2:weights=0.5 0.5,highpass=f=200,lowpass=f=8000[C];"
                    "[FL][FR]amix=inputs=2:weights=0.5 0.5,lowpass=f=120[LFE];"
                    "[FL]adelay=15,highpass=f=300,lowpass=f=10000,volume=0.8[RL];"
                    "[FR]adelay=15,highpass=f=300,lowpass=f=10000,volume=0.8[RR];"
                    "[FL][FR][C][LFE][RL][RR]amerge=inputs=6[out]"
                )
            else:
                return False
            
            cmd = [
                'ffmpeg', '-i', input_path,
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-c:a', 'pcm_s24le',
                '-ar', '48000',
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error applying surround upmix: {e}")
            return False
    
    def _convert_final_format(self, input_path: str, output_path: str) -> bool:
        """Convert processed audio to final format"""
        try:
            _, ext = os.path.splitext(output_path)
            
            if ext.lower() == '.flac':
                cmd = [
                    'ffmpeg', '-i', input_path,
                    '-c:a', 'flac',
                    '-compression_level', '8',
                    '-y', output_path
                ]
            elif ext.lower() == '.mp3':
                cmd = [
                    'ffmpeg', '-i', input_path,
                    '-c:a', 'libmp3lame',
                    '-b:a', '320k',
                    '-y', output_path
                ]
            else:
                cmd = ['ffmpeg', '-i', input_path, '-y', output_path]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error converting final format: {e}")
            return False
    
    def get_audio_info(self, file_path: str) -> Dict[str, Any]:
        """Get detailed audio file information"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {}
            
        except Exception as e:
            logger.error(f"Error getting audio info: {e}")
            return {}

class AudioProcessingError(Exception):
    """Base exception for audio processing errors"""
    pass

class FFmpegError(AudioProcessingError):
    """Raised when FFmpeg encounters an error"""
    pass

class AudioFileError(AudioProcessingError):
    """Raised when there's an issue with an audio file"""
    pass

@dataclass
class AudioStats:
    """Information about an audio file's technical properties"""
    channels: int
    sample_rate: int
    bit_depth: int
    duration: float
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    container: Optional[str] = None
    
    @property
    def is_surround(self) -> bool:
        """Check if this is surround audio (more than 2 channels)"""
        return self.channels > 2
    
    @property
    def is_high_res(self) -> bool:
        """Check if this is high resolution audio (>44.1kHz, >16-bit)"""
        return self.sample_rate > 44100 and self.bit_depth > 16

@dataclass
class AudioQuality:
    """Audio quality assessment metrics"""
    noise_level: float = 0.0      # 0.0 (clean) to 1.0 (very noisy)
    dynamics: float = 0.0         # 0.0 (compressed) to 1.0 (dynamic)
    rms_level: float = -60.0      # dB RMS level
    peak_level: float = -60.0     # dB peak level
    clipping: float = 0.0         # 0.0 (no clipping) to 1.0 (severe)
    distortion: float = 0.0       # 0.0 (clean) to 1.0 (distorted)

class EnhancedAudioProcessor:
    """Enhanced audio processor with advanced algorithms"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the enhanced audio processor"""
        self.config = config
        self.ffmpeg_path = self._get_ffmpeg_path(config)
        self.ffprobe_path = self._get_ffprobe_path(config)
        
        # Validate FFmpeg installation
        if not self._validate_ffmpeg():
            logger.warning("FFmpeg validation failed. Audio processing will be limited.")
            
        # Configure processing options
        self.temp_dir = config.get('temp_dir', tempfile.gettempdir())
        self.high_quality = config.get('high_quality_audio', True)
        self.processing_threads = config.get('processing_threads', min(os.cpu_count() or 2, 4))
            
    def _get_ffmpeg_path(self, config: Dict[str, Any]) -> str:
        """Get platform-specific FFmpeg binary path"""
        ffmpeg_location = config.get("ffmpeg_location", "")
        
        if ffmpeg_location:
            binary = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
            return os.path.join(ffmpeg_location, binary)
        
        return "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        
    def _get_ffprobe_path(self, config: Dict[str, Any]) -> str:
        """Get platform-specific FFprobe binary path"""
        ffmpeg_location = config.get("ffmpeg_location", "")
        
        if ffmpeg_location:
            binary = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
            return os.path.join(ffmpeg_location, binary)
        
        return "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
    
    def _validate_ffmpeg(self) -> bool:
        """Validate FFmpeg installation"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg validation failed: {result.stderr}")
                return False
                
            return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"FFmpeg validation failed: {e}")
            return False
            
    async def _run_ffmpeg(self, args: List[str], desc: str) -> bool:
        """Run FFmpeg command with progress monitoring"""
        cmd = [self.ffmpeg_path, "-y", "-hide_banner"] + args
        logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_message = stderr.decode()
                logger.error(f"FFmpeg {desc} failed: {error_message}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"FFmpeg {desc} error: {str(e)}")
            return False
    
    async def analyze_audio_quality(self, input_file: str) -> Optional[AudioQuality]:
        """
        Analyze audio quality using librosa for spectral analysis
        
        Args:
            input_file: Path to audio file
            
        Returns:
            AudioQuality object with detailed metrics
        """
        if not ENHANCED_PROCESSING_AVAILABLE:
            logger.warning("Enhanced processing libraries not available for quality analysis")
            return None
            
        try:
            # Load audio with librosa
            y, sr = librosa.load(input_file, sr=None, mono=False)
            
            # Handle stereo/mono conversion for analysis
            y_mono = librosa.to_mono(y) if y.ndim > 1 else y
                
            # Calculate quality metrics
            spectral_centroids = librosa.feature.spectral_centroid(y=y_mono, sr=sr)[0]
            noise_level = min(1.0, np.std(spectral_centroids) / 2000.0)
            
            # Dynamic range analysis
            rms = librosa.feature.rms(y=y_mono)[0]
            rms_db = librosa.amplitude_to_db(rms)
            dynamics = min(1.0, np.std(rms_db) / 20.0)
            
            # Level measurements
            rms_level = float(np.mean(rms_db))
            peak_level = float(librosa.amplitude_to_db(np.max(np.abs(y_mono))))
            
            # Clipping detection
            clipping_threshold = 0.99
            clipped_samples = np.sum(np.abs(y_mono) > clipping_threshold)
            clipping = min(1.0, clipped_samples / len(y_mono) * 1000)
            
            # Distortion estimation using zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(y_mono)[0]
            distortion = min(1.0, np.std(zcr) * 50)
            
            return AudioQuality(
                noise_level=float(noise_level),
                dynamics=float(dynamics),
                rms_level=rms_level,
                peak_level=peak_level,
                clipping=float(clipping),
                distortion=float(distortion)
            )
            
        except Exception as e:
            logger.error(f"Error analyzing audio quality for {input_file}: {e}")
            return None
    
    async def advanced_7_1_upmix(self, input_file: str) -> bool:
        """
        Advanced 7.1 upmix using psychoacoustic principles
        
        This method uses spectral analysis to create optimal channel placement
        with frequency-dependent panning matrices and spatial processing.
        
        Args:
            input_file: Path to input audio file
            
        Returns:
            Success status
        """
        if not ENHANCED_PROCESSING_AVAILABLE:
            logger.info("Enhanced libraries not available, using standard processing")
            return await self._standard_7_1_upmix(input_file)
            
        try:
            logger.info("Applying advanced psychoacoustic 7.1 upmix to %s", input_file)
            
            # Load and analyze audio
            y, sr = librosa.load(input_file, sr=None, mono=False)
            
            # Analyze spectral content for intelligent processing
            y_mono = librosa.to_mono(y) if y.ndim > 1 else y
                
            # Extract psychoacoustic features
            spectral_centroids = librosa.feature.spectral_centroid(y=y_mono, sr=sr)[0]
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y_mono, sr=sr)[0]
            
            # Determine content type for optimized processing
            avg_centroid = np.mean(spectral_centroids)
            avg_bandwidth = np.mean(spectral_bandwidth)
            
            # Choose processing profile based on content analysis
            if avg_centroid > 3000 and avg_bandwidth > 2000:
                # Voice/speech content
                content_type = "voice"
                center_boost = 0.25
                surround_mix = 0.1
            elif avg_centroid < 1500:
                # Bass-heavy music
                content_type = "bass_music"
                center_boost = 0.15
                surround_mix = 0.3
            else:
                # General music
                content_type = "music"
                center_boost = 0.15
                surround_mix = 0.2
                
            logger.info("Detected content type: %s", content_type)
            
            # Create advanced filter chain
            output_file = f"{os.path.splitext(input_file)[0]}_advanced_7.1{os.path.splitext(input_file)[1]}"
            
            # Build filter chain
            filter_parts = [
                "aformat=sample_fmts=fltp:sample_rates=96000:channel_layouts=7.1",
                f"pan=7.1|FL=FL+{center_boost}*FC+{surround_mix}*SL+0.05*LFE|FR=FR+{center_boost}*FC+{surround_mix}*SR+0.05*LFE|FC=FC+0.1*FL+0.1*FR|LFE=0.6*FL+0.6*FR+0.3*FC|BL=0.5*FL+{surround_mix*2}*SL+0.15*FC+0.1*LFE|BR=0.5*FR+{surround_mix*2}*SR+0.15*FC+0.1*LFE|SL=0.6*FL-0.1*FC+0.2*BL|SR=0.6*FR-0.1*FC+0.2*BR",
                "afir=dry=7:wet=12:length=1024:gtype=hann",
                "equalizer=f=60:t=h:width=60:g=3",
                "equalizer=f=150:t=h:width=100:g=2",
                "equalizer=f=3000:t=h:width=500:g=1.5",
                "equalizer=f=8000:t=h:width=2000:g=1",
                "equalizer=f=15000:t=h:width=5000:g=0.5",
                "extrastereo=m=1.2",
                "aecho=0.8:0.9:40:0.3|0.8:0.9:60:0.2",
                "dynaudnorm=f=10:g=3:p=0.9:m=10:r=0.5:b=1",
                "highpass=f=20",
                "lowpass=f=22000"
            ]
            
            args = [
                "-i", input_file,
                "-af", ",".join(filter_parts),
                "-c:a", "flac",
                "-sample_fmt", "s32",
                "-ar", "96000",
                "-compression_level", "8",
                output_file
            ]
            
            success = await self._run_ffmpeg(args, "advanced 7.1 upmix")
            if success:
                os.replace(output_file, input_file)
                logger.info("Advanced 7.1 upmix completed for %s", input_file)
            
            return success
            
        except Exception as e:
            logger.error(f"Error in advanced 7.1 upmix: {e}")
            return await self._standard_7_1_upmix(input_file)
    
    async def _standard_7_1_upmix(self, input_file: str) -> bool:
        """Standard 7.1 upmix fallback"""
        output_file = f"{os.path.splitext(input_file)[0]}_7.1{os.path.splitext(input_file)[1]}"
        
        filter_chain = [
            "aformat=sample_fmts=fltp:sample_rates=96000:channel_layouts=7.1",
            "pan=7.1|FL=FL+0.15*FC+0.1*SL|FR=FR+0.15*FC+0.1*SR|FC=FC+0.05*FL+0.05*FR|LFE=0.5*FL+0.5*FR+0.2*FC|BL=0.6*FL+0.3*SL+0.1*FC|BR=0.6*FR+0.3*SR+0.1*FC|SL=0.7*FL-0.2*FC+0.1*BL|SR=0.7*FR-0.2*FC+0.1*BR",
            "afir=dry=8:wet=10:length=500:gtype=sine"
        ]
        
        args = [
            "-i", input_file,
            "-af", ",".join(filter_chain),
            "-c:a", "flac",
            "-sample_fmt", "s32",
            "-ar", "96000",
            output_file
        ]
        
        success = await self._run_ffmpeg(args, "standard 7.1 upmix")
        if success:
            os.replace(output_file, input_file)
            
        return success
    
    async def ai_enhanced_denoise(self, input_file: str, strength: float = 0.2) -> bool:
        """
        AI-enhanced noise reduction using noisereduce library
        
        Args:
            input_file: Path to input audio file
            strength: Denoising strength (0.0 to 1.0)
            
        Returns:
            Success status
        """
        if not ENHANCED_PROCESSING_AVAILABLE:
            logger.info("Enhanced libraries not available, using standard denoising")
            return await self._standard_denoise(input_file, strength)
            
        try:
            logger.info("Applying AI-enhanced noise reduction to %s", input_file)
            
            # Create temporary file for AI processing
            temp_ai_file = f"{input_file}.ai_denoise.wav"
            
            # Load audio for AI processing
            y, sr = librosa.load(input_file, sr=None, mono=False)
            
            # Apply AI-based noise reduction
            strength_clamped = max(0.0, min(1.0, strength))
            
            if y.ndim > 1:
                # Process each channel separately
                processed_channels = []
                for i in range(y.shape[0]):
                    channel_data = y[i]
                    reduced_noise = nr.reduce_noise(
                        y=channel_data, 
                        sr=sr,
                        prop_decrease=strength_clamped * 0.8,
                        stationary=False,
                        n_fft=2048,
                        win_length=512,
                        hop_length=128
                    )
                    processed_channels.append(reduced_noise)
                
                processed_audio = np.array(processed_channels)
            else:
                # Mono processing
                processed_audio = nr.reduce_noise(
                    y=y, 
                    sr=sr,
                    prop_decrease=strength_clamped * 0.8,
                    stationary=False,
                    n_fft=2048,
                    win_length=512,
                    hop_length=128
                )
            
            # Save AI-processed audio
            sf.write(temp_ai_file, processed_audio.T if processed_audio.ndim > 1 else processed_audio, sr)
            
            # Apply additional FFmpeg-based refinement
            output_file = f"{input_file}.ai_enhanced"
            
            filter_chain = [
                "anlmdn=s=3:p=0.001:m=8:b=128",
                "dynaudnorm=f=10:g=3:p=0.95:m=15:r=0.3",
                "highpass=f=10",
                "equalizer=f=2000:t=h:width=200:g=0.5"
            ]
            
            args = [
                "-i", temp_ai_file,
                "-af", ",".join(filter_chain),
                "-c:a", "flac",
                "-compression_level", "8",
                output_file
            ]
            
            success = await self._run_ffmpeg(args, "AI denoise refinement")
            
            # Cleanup and replace
            if os.path.exists(temp_ai_file):
                os.remove(temp_ai_file)
                
            if success:
                os.replace(output_file, input_file)
                logger.info("AI-enhanced denoising completed for %s", input_file)
            
            return success
            
        except Exception as e:
            logger.error(f"Error in AI-enhanced denoising: {e}")
            return await self._standard_denoise(input_file, strength)
    
    async def _standard_denoise(self, input_file: str, strength: float = 0.2) -> bool:
        """Standard denoising fallback"""
        output_file = f"{input_file}.denoised"
        strength = max(0.0, min(1.0, strength))
        
        s_value = int(3 + (strength * 8))
        p_value = 0.001 + (strength * 0.004)
        m_value = int(10 + (strength * 20))
        
        filter_chain = [
            f"afftdn=nr={int(strength*50)}:nf={int(strength*20)}:tn=1",
            f"anlmdn=s={s_value}:p={p_value:.6f}:m={m_value}:b=256"
        ]
        
        args = [
            "-i", input_file,
            "-af", ",".join(filter_chain),
            "-c:a", "flac",
            output_file
        ]
        
        success = await self._run_ffmpeg(args, "standard denoising")
        if success:
            os.replace(output_file, input_file)
            
        return success
    async def professional_normalize(self, input_file: str, target_lufs: float = -14.0) -> bool:
        """
        Professional loudness normalization using pyloudnorm
        
        Args:
            input_file: Path to input audio file
            target_lufs: Target integrated loudness in LUFS
            
        Returns:
            Success status
        """
        if not ENHANCED_PROCESSING_AVAILABLE:
            logger.info("Enhanced libraries not available, using standard normalization")
            return await self._standard_normalize(input_file, target_lufs)
            
        try:
            logger.info("Applying professional loudness normalization to %s (target: %.1f LUFS)", input_file, target_lufs)
            
            # Load and analyze audio
            current_lufs = await self._get_current_loudness(input_file)
            
            # Check if normalization is needed
            if abs(current_lufs - target_lufs) <= 0.5:
                logger.info("Audio already within target range")
                return True
                
            # Apply normalization
            return await self._apply_professional_normalization(input_file, current_lufs, target_lufs)
                
        except Exception as e:
            logger.error("Error in professional normalization: %s", e)
            return await self._standard_normalize(input_file, target_lufs)
    
    async def _get_current_loudness(self, input_file: str) -> float:
        """Get current loudness using pyloudnorm"""
        y, sr = librosa.load(input_file, sr=None, mono=False)
        meter = pyln.Meter(sr)
        
        # Prepare audio for measurement
        if y.ndim > 1:
            y_for_measurement = y.T
        else:
            y_for_measurement = y.reshape(-1, 1)
        
        current_lufs = meter.integrated_loudness(y_for_measurement)
        logger.info("Current LUFS: %.1f", current_lufs)
        return current_lufs
    
    async def _apply_professional_normalization(self, input_file: str, current_lufs: float, target_lufs: float) -> bool:
        """Apply professional normalization with pyloudnorm"""
        # Load audio
        y, sr = librosa.load(input_file, sr=None, mono=False)
        
        # Prepare audio for measurement
        if y.ndim > 1:
            y_for_measurement = y.T
        else:
            y_for_measurement = y.reshape(-1, 1)
        
        # Normalize audio using pyloudnorm
        normalized_audio = pyln.normalize.loudness(y_for_measurement, current_lufs, target_lufs)
        
        # Convert back to original format
        if y.ndim > 1:
            normalized_audio = normalized_audio.T
        else:
            normalized_audio = normalized_audio.flatten()
        
        # Save and process with FFmpeg
        return await self._finalize_professional_normalization(input_file, normalized_audio, sr)
    
    async def _finalize_professional_normalization(self, input_file: str, normalized_audio, sr: int) -> bool:
        """Finalize professional normalization with FFmpeg processing"""
        temp_file = f"{input_file}.pyloudnorm.wav"
        
        # Save normalized audio to temporary file
        if normalized_audio.ndim > 1:
            sf.write(temp_file, normalized_audio.T, sr)
        else:
            sf.write(temp_file, normalized_audio, sr)
        
        # Apply final processing with FFmpeg
        output_file = f"{input_file}.pro_normalized"
        
        filter_chain = [
            "alimiter=level_in=1:level_out=1:limit=-1.0:attack=5:release=50:asc=1",
            "dynaudnorm=f=10:g=3:p=0.95:m=20:r=0.4:b=1"
        ]
        
        args = [
            "-i", temp_file,
            "-af", ",".join(filter_chain),
            "-c:a", "flac",
            "-compression_level", "8",
            output_file
        ]
        
        success = await self._run_ffmpeg(args, "professional normalization")
        
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        if success:
            os.replace(output_file, input_file)
            logger.info("Professional normalization completed")
        
        return success
    
    async def _standard_normalize(self, input_file: str, target_lufs: float = -14.0) -> bool:
        """Standard normalization fallback"""
        output_file = f"{input_file}.normalized"
        
        filter_chain = [
            f"loudnorm=I={target_lufs}:TP=-1:LRA=11:print_format=summary"
        ]
        
        args = [
            "-i", input_file,
            "-af", ",".join(filter_chain),
            "-c:a", "flac",
            output_file
        ]
        
        success = await self._run_ffmpeg(args, "standard normalization")
        if success:
            os.replace(output_file, input_file)
            
        return success
    
    async def validate_flac_integrity(self, file_path: str) -> bool:
        """
        Validate FLAC file integrity and lossless encoding
        
        Args:
            file_path: Path to FLAC file
            
        Returns:
            True if file is valid and truly lossless
        """
        if not ENHANCED_PROCESSING_AVAILABLE:
            logger.warning("Enhanced FLAC validation not available, using basic checks")
            return os.path.exists(file_path) and file_path.lower().endswith(FLAC_EXT)
            
        try:
            # Check if file exists and has FLAC extension
            if not os.path.exists(file_path) or not file_path.lower().endswith(FLAC_EXT):
                logger.error(f"File is not a valid FLAC file: {file_path}")
                return False
            
            # Use soundfile to validate FLAC structure
            try:
                info = sf.info(file_path)
                logger.info(f"FLAC file info - Channels: {info.channels}, Sample Rate: {info.samplerate}, "
                           f"Frames: {info.frames}, Format: {info.format}")
                
                # Verify it's actually FLAC format
                if 'FLAC' not in info.format:
                    logger.error(f"File is not in FLAC format: {info.format}")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to read FLAC file structure: {e}")
                return False
            
            # Load a small sample to verify readability
            try:
                # Load first 5 seconds to test integrity
                duration_limit = min(5.0, info.frames / info.samplerate)
                y, _ = librosa.load(file_path, sr=None, duration=duration_limit)
                
                # Check for obvious corruption
                if np.all(y == 0):
                    logger.error("FLAC file contains only silence - possible corruption")
                    return False
                    
                # Check for excessive clipping
                clipping_threshold = 0.95
                clipped_samples = np.sum(np.abs(y) > clipping_threshold)
                clipping_ratio = clipped_samples / len(y)
                
                if clipping_ratio > 0.01:  # More than 1% clipped samples
                    logger.warning(f"FLAC file has high clipping ratio ({clipping_ratio:.2%}) - "
                                 "may not be true lossless")
                
                # Analyze compression characteristics
                file_size = os.path.getsize(file_path)
                uncompressed_size = info.frames * info.channels * 3  # Assuming 24-bit equivalent
                compression_ratio = file_size / uncompressed_size
                
                # Typical FLAC compression ratios: 0.4-0.7 for music
                if compression_ratio < 0.3:
                    logger.warning(f"Unusually high compression ratio ({compression_ratio:.2f}) - "
                                 "may indicate lossy source")
                elif compression_ratio > 0.8:
                    logger.warning(f"Low compression ratio ({compression_ratio:.2f}) - "
                                 "may indicate inefficient encoding")
                
                logger.info(f"FLAC validation passed - Compression ratio: {compression_ratio:.2f}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to validate FLAC audio content: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating FLAC integrity: {e}")
            return False
    
    async def apply_enhanced_processing_chain(self, input_file: str, options: Dict[str, Any]) -> bool:
        """
        Apply complete enhanced audio processing chain
        
        Processing order:
        1. Quality analysis and validation
        2. AI-enhanced noise reduction (if requested)
        3. Advanced 7.1 upmix (if requested)
        4. Professional loudness normalization
        5. Final validation and integrity check
        
        Args:
            input_file: Path to input audio file
            options: Processing options dictionary
            
        Returns:
            Success status
        """
        logger.info(f"Starting enhanced audio processing chain for {input_file}")
        
        try:
            # Step 1: Initial quality analysis
            quality = await self.analyze_audio_quality(input_file)
            if quality:
                logger.info(f"Initial quality - Noise: {quality.noise_level:.2f}, "
                           f"Dynamics: {quality.dynamics:.2f}, RMS: {quality.rms_level:.1f}dB")
            
            # Step 2: AI-enhanced denoising (if requested)
            if options.get('denoise_audio', False):
                denoise_strength = options.get('denoise_strength', 0.2)
                logger.info(f"Applying AI-enhanced denoising (strength: {denoise_strength})")
                
                if not await self.ai_enhanced_denoise(input_file, denoise_strength):
                    logger.warning("AI-enhanced denoising failed")
            
            # Step 3: Advanced 7.1 upmix (if requested)  
            if options.get('upmix_audio', False):
                logger.info("Applying advanced psychoacoustic 7.1 upmix")
                
                if not await self.advanced_7_1_upmix(input_file):
                    logger.warning("Advanced 7.1 upmix failed")
            
            # Step 4: Professional normalization
            target_lufs = options.get('normalize_target', -14.0)
            logger.info(f"Applying professional loudness normalization (target: {target_lufs} LUFS)")
            
            if not await self.professional_normalize(input_file, target_lufs):
                logger.warning("Professional normalization failed")
            
            # Step 5: Final validation
            if input_file.lower().endswith(FLAC_EXT):
                logger.info("Validating FLAC integrity")
                if not await self.validate_flac_integrity(input_file):
                    logger.error("FLAC integrity validation failed")
                    return False
            
            # Final quality check
            final_quality = await self.analyze_audio_quality(input_file)
            if final_quality and quality:
                logger.info(f"Processing completed - Quality improvement: "
                           f"Noise: {quality.noise_level:.2f} → {final_quality.noise_level:.2f}, "
                           f"Dynamics: {quality.dynamics:.2f} → {final_quality.dynamics:.2f}")
            
            logger.info(f"Enhanced audio processing chain completed successfully for {input_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error in enhanced processing chain: {e}")
            return False

# For backward compatibility, create alias
AudioProcessor = EnhancedAudioProcessor
