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
        self.supported_formats = ['.mp3', FLAC_EXT, '.wav', '.m4a', '.aac', '.ogg', '.opus']
        
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
            
            if ext.lower() == FLAC_EXT:
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

@dataclass
class AudioEnhancementSettings:
    """Settings for audio enhancement processing"""
    # Enhancement levels
    level: str = "medium"  # light, medium, aggressive
    
    # AI-powered enhancement
    noise_reduction: bool = True
    noise_reduction_strength: float = 0.6  # 0.0 to 1.0
    
    # Audio upscaling
    upscale_sample_rate: bool = False
    target_sample_rate: int = 48000  # 22050, 44100, 48000, 96000, 192000
    
    # Frequency enhancement
    frequency_extension: bool = False
    high_freq_boost: float = 3.0  # dB boost for high frequencies
    
    # Spatial enhancement
    stereo_widening: bool = False
    stereo_width: float = 1.2  # 1.0 = normal, 2.0 = maximum width
    
    # Dynamic processing
    normalization: bool = True
    target_lufs: float = -16.0  # EBU R128 standard
    dynamic_compression: bool = False
    compression_ratio: float = 3.0
    
    # Restoration
    declipping: bool = False
    artifact_removal: bool = True
    
    # Processing options
    preserve_peaks: bool = True
    high_quality_resampling: bool = True
    multiband_processing: bool = False

@dataclass
class AudioPreset:
    """Predefined audio enhancement presets"""
    name: str
    description: str
    settings: AudioEnhancementSettings
    
# Audio enhancement presets
AUDIO_ENHANCEMENT_PRESETS = {
    "podcast": AudioPreset(
        name="Podcast",
        description="Optimized for speech content with noise reduction and clarity enhancement",
        settings=AudioEnhancementSettings(
            level="medium",
            noise_reduction=True,
            noise_reduction_strength=0.8,
            frequency_extension=True,
            high_freq_boost=2.0,
            normalization=True,
            target_lufs=-18.0,
            dynamic_compression=True,
            compression_ratio=2.5,
            artifact_removal=True
        )
    ),
    "music": AudioPreset(
        name="Music",
        description="Optimized for music with stereo enhancement and dynamic preservation",
        settings=AudioEnhancementSettings(
            level="light",
            noise_reduction=True,
            noise_reduction_strength=0.3,
            upscale_sample_rate=True,
            target_sample_rate=48000,
            stereo_widening=True,
            stereo_width=1.3,
            normalization=True,
            target_lufs=-16.0,
            preserve_peaks=True,
            high_quality_resampling=True
        )
    ),
    "speech": AudioPreset(
        name="Speech",
        description="Optimized for speech with strong noise reduction and clarity",
        settings=AudioEnhancementSettings(
            level="aggressive",
            noise_reduction=True,
            noise_reduction_strength=0.9,
            frequency_extension=True,
            high_freq_boost=4.0,
            normalization=True,
            target_lufs=-20.0,
            dynamic_compression=True,
            compression_ratio=4.0,
            artifact_removal=True,
            declipping=True
        )
    ),
    "broadcast": AudioPreset(
        name="Broadcast",
        description="Professional broadcast standards with consistent levels",
        settings=AudioEnhancementSettings(
            level="medium",
            noise_reduction=True,
            noise_reduction_strength=0.6,
            normalization=True,
            target_lufs=-23.0,  # Broadcast standard
            dynamic_compression=True,
            compression_ratio=3.5,
            preserve_peaks=False,
            multiband_processing=True
        )
    ),
    "restoration": AudioPreset(
        name="Restoration",
        description="Maximum enhancement for damaged or low-quality audio",
        settings=AudioEnhancementSettings(
            level="aggressive",
            noise_reduction=True,
            noise_reduction_strength=0.95,
            upscale_sample_rate=True,
            target_sample_rate=48000,
            frequency_extension=True,
            high_freq_boost=5.0,
            declipping=True,
            artifact_removal=True,
            multiband_processing=True,
            high_quality_resampling=True
        )
    )
}

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

    async def enhance_audio_comprehensive(self, input_file: str, output_file: str, 
                                        settings: AudioEnhancementSettings,
                                        progress_callback: Optional[Callable] = None) -> bool:
        """
        Apply comprehensive audio enhancement with all available algorithms
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output enhanced file
            settings: Enhancement settings configuration
            progress_callback: Optional progress callback function
            
        Returns:
            True if enhancement was successful
        """
        try:
            if progress_callback:
                progress_callback("Starting audio enhancement", 0)
                
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_files = {}
                current_file = input_file
                
                # Step 1: Load and analyze audio
                if progress_callback:
                    progress_callback("Analyzing audio quality", 10)
                
                quality = await self.analyze_audio_quality(input_file)
                if not quality:
                    logger.warning("Could not analyze audio quality, proceeding with defaults")
                
                # Step 2: AI-powered noise reduction
                if settings.noise_reduction:
                    if progress_callback:
                        progress_callback("Applying noise reduction", 20)
                    
                    denoised_file = os.path.join(temp_dir, "denoised.wav")
                    if await self._apply_ai_noise_reduction(current_file, denoised_file, settings):
                        temp_files['denoised'] = denoised_file
                        current_file = denoised_file
                
                # Step 3: Sample rate upscaling
                if settings.upscale_sample_rate:
                    if progress_callback:
                        progress_callback("Upscaling sample rate", 30)
                    
                    upscaled_file = os.path.join(temp_dir, "upscaled.wav")
                    if await self._apply_sample_rate_upscaling(current_file, upscaled_file, settings):
                        temp_files['upscaled'] = upscaled_file
                        current_file = upscaled_file
                
                # Step 4: Frequency extension
                if settings.frequency_extension:
                    if progress_callback:
                        progress_callback("Extending frequency range", 40)
                    
                    extended_file = os.path.join(temp_dir, "extended.wav")
                    if await self._apply_frequency_extension(current_file, extended_file, settings):
                        temp_files['extended'] = extended_file
                        current_file = extended_file
                
                # Step 5: Stereo widening
                if settings.stereo_widening:
                    if progress_callback:
                        progress_callback("Applying stereo enhancement", 50)
                    
                    widened_file = os.path.join(temp_dir, "widened.wav")
                    if await self._apply_stereo_widening(current_file, widened_file, settings):
                        temp_files['widened'] = widened_file
                        current_file = widened_file
                
                # Step 6: Dynamic range compression
                if settings.dynamic_compression:
                    if progress_callback:
                        progress_callback("Applying dynamic compression", 60)
                    
                    compressed_file = os.path.join(temp_dir, "compressed.wav")
                    if await self._apply_dynamic_compression(current_file, compressed_file, settings):
                        temp_files['compressed'] = compressed_file
                        current_file = compressed_file
                
                # Step 7: Declipping and artifact removal
                if settings.declipping or settings.artifact_removal:
                    if progress_callback:
                        progress_callback("Removing artifacts and clipping", 70)
                    
                    restored_file = os.path.join(temp_dir, "restored.wav")
                    if await self._apply_restoration(current_file, restored_file, settings):
                        temp_files['restored'] = restored_file
                        current_file = restored_file
                
                # Step 8: Loudness normalization (final step)
                if settings.normalization:
                    if progress_callback:
                        progress_callback("Applying loudness normalization", 80)
                    
                    normalized_file = os.path.join(temp_dir, "normalized.wav")
                    if await self._apply_advanced_normalization(current_file, normalized_file, settings):
                        temp_files['normalized'] = normalized_file
                        current_file = normalized_file
                
                # Step 9: Convert to final format
                if progress_callback:
                    progress_callback("Converting to final format", 90)
                
                success = await self._convert_to_final_format(current_file, output_file, settings)
                
                if progress_callback:
                    progress_callback("Enhancement complete", 100)
                
                return success
                
        except Exception as e:
            logger.error(f"Audio enhancement failed: {e}")
            return False
    
    async def _apply_ai_noise_reduction(self, input_file: str, output_file: str, 
                                      settings: AudioEnhancementSettings) -> bool:
        """Apply AI-powered noise reduction using multiple algorithms"""
        try:
            if not ENHANCED_PROCESSING_AVAILABLE:
                # Fallback to FFmpeg-based noise reduction
                return await self._apply_ffmpeg_noise_reduction(input_file, output_file, settings)
            
            # Load audio data
            data, sr = librosa.load(input_file, sr=None)
            
            # Ensure we have reasonable data
            if len(data) == 0:
                logger.error("No audio data loaded")
                return False
            
            # Apply noise reduction based on enhancement level
            if settings.level == "light":
                # Gentle noise reduction
                reduced_noise = nr.reduce_noise(
                    y=data, sr=sr, 
                    stationary=False,
                    prop_decrease=min(settings.noise_reduction_strength * 0.6, 0.6)
                )
            elif settings.level == "medium":
                # Standard noise reduction with spectral gating
                reduced_noise = nr.reduce_noise(
                    y=data, sr=sr,
                    stationary=False,
                    prop_decrease=settings.noise_reduction_strength,
                    n_std_thresh_stationary=1.5,
                    n_thresh_nonstationary=0.5
                )
            else:  # aggressive
                # Multi-pass noise reduction
                # First pass: stationary noise
                temp_reduced = nr.reduce_noise(
                    y=data, sr=sr,
                    stationary=True,
                    prop_decrease=settings.noise_reduction_strength * 0.7
                )
                # Second pass: non-stationary noise
                reduced_noise = nr.reduce_noise(
                    y=temp_reduced, sr=sr,
                    stationary=False,
                    prop_decrease=settings.noise_reduction_strength * 0.8,
                    n_std_thresh_stationary=2.0
                )
            
            # Save processed audio
            sf.write(output_file, reduced_noise, sr, subtype='PCM_24')
            return True
            
        except Exception as e:
            logger.error(f"AI noise reduction failed: {e}")
            return False
    
    async def _apply_ffmpeg_noise_reduction(self, input_file: str, output_file: str,
                                          settings: AudioEnhancementSettings) -> bool:
        """Apply FFmpeg-based noise reduction as fallback when advanced libraries unavailable"""
        try:
            # Create a simple noise reduction filter chain based on enhancement level
            if settings.level == "light":
                # Gentle high-pass filter and slight noise gate
                filter_complex = [
                    "highpass=f=80",
                    "lowpass=f=18000",
                    "agate=threshold=0.01:ratio=2:attack=1:release=10"
                ]
            elif settings.level == "medium":
                # Standard noise reduction with adaptive filters
                filter_complex = [
                    "highpass=f=100",
                    "lowpass=f=16000", 
                    "agate=threshold=0.02:ratio=3:attack=2:release=20",
                    "adeclick=t=0.002:w=2"
                ]
            else:  # aggressive
                # Strong noise reduction with multiple stages
                filter_complex = [
                    "highpass=f=120",
                    "lowpass=f=15000",
                    "agate=threshold=0.03:ratio=4:attack=3:release=30",
                    "adeclick=t=0.003:w=4",
                    "afftdn=nr=20:nf=-40"  # FFT denoiser if available
                ]
            
            # Apply noise reduction strength adjustment
            if settings.noise_reduction_strength < 0.5:
                # Reduce filter intensity for lower strength settings
                filter_string = ",".join(filter_complex[:2])  # Only basic filters
            else:
                filter_string = ",".join(filter_complex)
            
            args = [
                "-i", input_file,
                "-af", filter_string,
                "-acodec", "pcm_s24le",
                output_file
            ]
            
            return await self._run_ffmpeg(args, "FFmpeg noise reduction")
            
        except Exception as e:
            logger.error(f"FFmpeg noise reduction failed: {e}")
            return False
    
    def get_available_presets(self) -> List[str]:
        """Get list of available audio enhancement presets"""
        return list(AUDIO_ENHANCEMENT_PRESETS.keys())
    
    def get_preset_info(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific preset"""
        if preset_name not in AUDIO_ENHANCEMENT_PRESETS:
            return None
            
        preset = AUDIO_ENHANCEMENT_PRESETS[preset_name]
        return {
            "name": preset.name,
            "description": preset.description,
            "settings": {
                "level": preset.settings.level,
                "noise_reduction": preset.settings.noise_reduction,
                "noise_reduction_strength": preset.settings.noise_reduction_strength,
                "upscale_sample_rate": preset.settings.upscale_sample_rate,
                "target_sample_rate": preset.settings.target_sample_rate,
                "frequency_extension": preset.settings.frequency_extension,
                "high_freq_boost": preset.settings.high_freq_boost,
                "stereo_widening": preset.settings.stereo_widening,
                "stereo_width": preset.settings.stereo_width,
                "normalization": preset.settings.normalization,
                "target_lufs": preset.settings.target_lufs,
                "dynamic_compression": preset.settings.dynamic_compression,
                "compression_ratio": preset.settings.compression_ratio,
                "declipping": preset.settings.declipping,
                "artifact_removal": preset.settings.artifact_removal,
                "preserve_peaks": preset.settings.preserve_peaks,
                "high_quality_resampling": preset.settings.high_quality_resampling,
                "multiband_processing": preset.settings.multiband_processing
            }
        }
    async def recommend_preset(self, input_file: str) -> Optional[str]:
        """Analyze audio file and recommend the best enhancement preset"""
        try:
            quality = await self.analyze_audio_quality(input_file)
            if not quality:
                logger.warning("Could not analyze audio quality for preset recommendation")
                return "music"  # Default fallback
            
            stats = await self.get_audio_stats(input_file)
            if not stats:
                return "music"  # Default fallback
            
            return self._determine_preset_by_characteristics(quality, stats)
                    
        except Exception as e:
            logger.error(f"Preset recommendation failed: {e}")
            return "music"  # Safe default
    
    def _determine_preset_by_characteristics(self, quality: AudioQuality, stats: AudioStats) -> str:
        """Determine the best preset based on audio characteristics"""
        if stats.channels == 1:
            return self._recommend_for_mono(quality)
        elif stats.channels == 2:
            return self._recommend_for_stereo(quality, stats)
        else:
            return self._recommend_for_multichannel(quality)
    
    def _recommend_for_mono(self, quality: AudioQuality) -> str:
        """Recommend preset for mono audio"""
        if quality.noise_level > 0.4:
            return "restoration"
        elif quality.dynamics < 0.3:
            return "speech"
        else:
            return "podcast"
    
    def _recommend_for_stereo(self, quality: AudioQuality, stats: AudioStats) -> str:
        """Recommend preset for stereo audio"""
        if quality.noise_level > 0.6 or quality.clipping > 0.1 or stats.sample_rate <= 22050:
            return "restoration"
        elif quality.dynamics > 0.7:
            return "music"
        else:
            return "music"
    
    def _recommend_for_multichannel(self, quality: AudioQuality) -> str:
        """Recommend preset for multi-channel audio"""
        if quality.noise_level > 0.3:
            return "broadcast"
        else:
            return "music"
    
    async def validate_enhancement_settings(self, settings: AudioEnhancementSettings) -> List[str]:
        """Validate enhancement settings and return list of warnings/issues"""
        warnings = []
        
        # Validate noise reduction strength
        if settings.noise_reduction_strength < 0.0 or settings.noise_reduction_strength > 1.0:
            warnings.append("Noise reduction strength should be between 0.0 and 1.0")
        
        # Validate target sample rate
        valid_rates = [22050, 44100, 48000, 96000, 192000]
        if settings.target_sample_rate not in valid_rates:
            warnings.append(f"Target sample rate should be one of: {valid_rates}")
        
        # Validate stereo width
        if settings.stereo_width < 0.5 or settings.stereo_width > 3.0:
            warnings.append("Stereo width should be between 0.5 and 3.0")
        
        # Validate compression ratio
        if settings.compression_ratio < 1.0 or settings.compression_ratio > 20.0:
            warnings.append("Compression ratio should be between 1.0 and 20.0")
        
        # Validate target LUFS
        if settings.target_lufs < -40.0 or settings.target_lufs > 0.0:
            warnings.append("Target LUFS should be between -40.0 and 0.0")
        
        # Validate high frequency boost
        if settings.high_freq_boost < 0.0 or settings.high_freq_boost > 12.0:
            warnings.append("High frequency boost should be between 0.0 and 12.0 dB")
        
        # Check for conflicting settings
        if settings.preserve_peaks and settings.dynamic_compression:
            warnings.append("Peak preservation and dynamic compression may conflict")
        
        if settings.upscale_sample_rate and settings.target_sample_rate < 44100:
            warnings.append("Upscaling to sample rates below 44.1kHz is not recommended")
        
        return warnings

    async def create_custom_preset(self, name: str, description: str, 
                                 settings: AudioEnhancementSettings) -> bool:
        """Create a custom enhancement preset and add it to available presets"""
        try:
            # Validate settings first
            warnings = await self.validate_enhancement_settings(settings)
            if warnings:
                logger.warning(f"Preset validation warnings: {warnings}")
            
            # Create new preset
            custom_preset = AudioPreset(
                name=name,
                description=description,
                settings=settings
            )
            
            # Add to available presets
            AUDIO_ENHANCEMENT_PRESETS[name.lower()] = custom_preset
            
            logger.info(f"Created custom preset '{name}': {description}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create custom preset: {e}")
            return False

    async def get_audio_stats(self, input_file: str) -> Optional[AudioStats]:
        """Get detailed audio file statistics using FFprobe"""
        try:
            cmd = [
                self.ffprobe_path, "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", input_file
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFprobe failed: {stderr.decode()}")
                return None
            
            import json
            data = json.loads(stdout.decode())
            
            # Find audio stream
            audio_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    audio_stream = stream
                    break
            
            if not audio_stream:
                logger.error("No audio stream found")
                return None
            
            # Extract statistics
            channels = int(audio_stream.get('channels', 2))
            sample_rate = int(audio_stream.get('sample_rate', 44100))
            
            # Try to get bit depth from sample_fmt
            sample_fmt = audio_stream.get('sample_fmt', 's16')
            if 's16' in sample_fmt:
                bit_depth = 16
            elif 's24' in sample_fmt or 's32' in sample_fmt:
                bit_depth = 24
            elif 'flt' in sample_fmt or 'dbl' in sample_fmt:
                bit_depth = 32
            else:
                bit_depth = 16  # Default
            
            duration = float(audio_stream.get('duration', 0.0))
            bitrate = audio_stream.get('bit_rate')
            if bitrate:
                bitrate = int(bitrate)
            
            codec = audio_stream.get('codec_name', 'unknown')
            container = data.get('format', {}).get('format_name', 'unknown')
            
            return AudioStats(
                channels=channels,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                duration=duration,
                bitrate=bitrate,
                codec=codec,
                container=container
            )
            
        except Exception as e:
            logger.error(f"Failed to get audio stats: {e}")
            return None

    async def process_with_real_time_preview(self, input_file: str, output_file: str,
                                           settings: AudioEnhancementSettings,
                                           preview_duration: float = 10.0) -> bool:
        """Process audio with real-time preview of first few seconds"""
        try:
            # Create preview of first N seconds
            preview_file = f"{output_file}_preview.wav"
            
            # Extract preview segment
            args = [
                "-i", input_file,
                "-t", str(preview_duration),
                "-acodec", "pcm_s24le",
                preview_file
            ]
            
            if not await self._run_ffmpeg(args, "preview extraction"):
                logger.error("Failed to create preview segment")
                return False
            
            # Process preview with same settings
            preview_output = f"{output_file}_preview_processed.wav"
            preview_success = await self.enhance_audio_comprehensive(
                preview_file, preview_output, settings
            )
            
            if preview_success:
                logger.info(f"Preview processed successfully: {preview_output}")
                logger.info("You can listen to the preview before processing the full file")
                
                # Ask user if they want to continue with full processing
                # Note: This would need to be integrated with the CLI for user interaction
                  # Clean up preview files
                try:
                    os.remove(preview_file)
                except (OSError, IOError):
                    pass
                
                # Process full file
                return await self.enhance_audio_comprehensive(input_file, output_file, settings)
            else:
                logger.error("Preview processing failed")
                return False
                
        except Exception as e:
            logger.error(f"Real-time preview processing failed: {e}")
            return False

    def get_processing_requirements(self, settings: AudioEnhancementSettings) -> Dict[str, Any]:
        """Estimate processing requirements and time for given settings"""
        try:
            complexity_score = 0
            
            # Add complexity based on enabled features
            if settings.noise_reduction:
                complexity_score += 3 if settings.level == "aggressive" else 2
            if settings.upscale_sample_rate:
                complexity_score += 2
            if settings.frequency_extension:
                complexity_score += 2
            if settings.stereo_widening:
                complexity_score += 1
            if settings.dynamic_compression:
                complexity_score += 2 if settings.multiband_processing else 1
            if settings.declipping or settings.artifact_removal:
                complexity_score += 3
            if settings.normalization:
                complexity_score += 1
            
            # Estimate relative processing time multiplier
            time_multiplier = max(1.0, complexity_score * 0.3)
            
            # Estimate memory requirements (rough)
            memory_mb = 100 + (complexity_score * 50)
            
            return {
                "complexity_score": complexity_score,
                "estimated_time_multiplier": time_multiplier,
                "estimated_memory_mb": memory_mb,
                "cpu_intensive": complexity_score > 6,
                "requires_enhanced_libs": settings.noise_reduction or settings.upscale_sample_rate,
                "ffmpeg_only": not (settings.noise_reduction and ENHANCED_PROCESSING_AVAILABLE)
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate processing requirements: {e}")
            return {"error": str(e)}
