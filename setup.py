from setuptools import setup, find_packages
from pathlib import Path

# Read version from __init__.py
init_path = Path(__file__).parent / "modules" / "__init__.py"
with open(init_path) as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"\'')
            break

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    with open(readme_path, encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="snatch-dl",
    version=version,
    description="A versatile media downloader with p2p support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Rashed AL-Othman",
    author_email="Rashed.m.alothman@gmail.com",
    url="https://github.com/Rashed-alothman/Snatch",
    license="MIT",
    keywords=["download", "media", "p2p", "youtube", "video"],
    packages=find_packages(include=["modules", "modules.*"]),
    package_data={
        "modules": [
            "config/*.json",
            "data/*.txt",
        ],
    },
    # Core dependencies
    install_requires=[
        "yt-dlp>=2025.4.30",
        "ffmpeg>=1.4",
        "mutagen>=1.47.0",
        "psutil>=7.0.0",
        
        # HTTP and networking
        "requests>=2.32.3",
        "urllib3>=2.4.0",
        "certifi>=2025.4.26",
        "charset-normalizer>=3.4.2",
        "idna>=3.10",
        
        # CLI interface and formatting
        "typer>=0.15.3",
        "click>=8.1.8",
        "rich>=14.0.0",
        "pyfiglet>=1.0.2",
        "colorama>=0.4.6",
        "tqdm>=4.66.1",
        "shellingham>=1.5.0",
        "prompt_toolkit>=3.0.43",
        
        # Markdown processing
        "markdown-it-py>=3.0.0",
        "mdurl>=0.1.2",
        "Pygments>=2.19.1",
        
        # Utilities
        "python-json-logger>=2.0.4",
        "asgiref>=3.8.1",
        "typing_extensions>=4.13.2",        # P2P and DHT support
        "cryptography>=44.0.3",
        "future>=1.0.0",
        "pyp2p>=0.8.3",
        "twisted>=24.11.0",
        "cffi>=1.17.1",
        "attrs>=25.3.0",
        "service_identity>=24.1.0",
        "netifaces>=0.11.0",
        "miniupnpc>=2.3.2",
        "u-msgpack-python>=2.8.0",  # Required by pyp2p
        "storjkademlia>=0.7.4",  # Required by pyp2p

        # Additional dependencies
        "hyperlink>=21.0.0",
        "imageio>=2.37.0",
        "imageio-ffmpeg>=0.6.0",
        "incremental>=24.7.2",
        "iniconfig>=2.1.0",
        "ipaddress>=1.0.23",
        "moviepy>=2.1.2",
        "netifaces>=0.11.0",
        "ntplib>=0.4.0",
        "numpy>=2.2.5",
        "packaging>=25.0",
        "pillow>=10.4.0",
        "pluggy>=1.5.0",
        "proglog>=0.1.12",
        "pycparser>=2.22",
        "pydub>=0.25.1",
        "pyroute2>=0.9.2",
        "Twisted>=24.11.0",
        "wcwidth>=0.2.13",
        "zope.interface>=7.2",
        "future>=1.0.0",
    ],
    
    entry_points={
        "console_scripts": [
            "snatch=modules.cli:main",
        ],
    },
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License", 
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Internet :: File Transfer Protocol (FTP)",
        "Topic :: Multimedia :: Video",
        "Topic :: Internet :: WWW/HTTP :: Downloaders",
    ],
    
    python_requires=">=3.8",
    project_urls={
        "Documentation": "https://github.com/Rashed-alothman/Snatch/wiki",
        "Source": "https://github.com/Rashed-alothman/Snatch",
        "Issue Tracker": "https://github.com/Rashed-alothman/Snatch/issues",
    },
)