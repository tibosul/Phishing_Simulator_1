#!/usr/bin/env python3
"""
Setup script for Phishing Simulator package
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "A professional phishing simulation and awareness training platform"

# Read requirements
def read_requirements():
    req_path = os.path.join(os.path.dirname(__file__), 'Phishing_Simulator', 'requirements.txt')
    if os.path.exists(req_path):
        with open(req_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="phishing-simulator",
    version="1.0.0",
    description="A professional phishing simulation and awareness training platform",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Phishing Simulator Team",
    author_email="admin@phishing-simulator.local",
    url="https://github.com/tibosul/Phishing_Simulator_1",
    
    # Package configuration
    packages=find_packages(where="Phishing_Simulator"),
    package_dir={"": "Phishing_Simulator"},
    include_package_data=True,
    
    # Dependencies
    install_requires=read_requirements(),
    
    # Python version requirement
    python_requires=">=3.8",
    
    # Classification
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Education", 
        "Topic :: Security",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Flask",
        "Operating System :: OS Independent",
    ],
    
    # Keywords
    keywords="phishing simulation security awareness training cybersecurity",
    
    # Entry points
    entry_points={
        "console_scripts": [
            "phishing-simulator=app:main",
        ],
    },
    
    # Package data
    package_data={
        "": ["*.html", "*.css", "*.js", "*.png", "*.jpg", "*.svg", "*.ico"],
    },
    
    # Project URLs
    project_urls={
        "Bug Reports": "https://github.com/tibosul/Phishing_Simulator_1/issues",
        "Source": "https://github.com/tibosul/Phishing_Simulator_1",
        "Documentation": "https://github.com/tibosul/Phishing_Simulator_1/wiki",
    },
    
    # License
    license="MIT",
    
    # Zip safe
    zip_safe=False,
    
    # Test suite
    test_suite="tests",
    
    # Additional metadata
    platforms=["any"],
    
    # Development dependencies
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.812",
        ],
        "test": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "coverage>=5.0",
        ],
    },
)