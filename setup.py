from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="vps-dev-agent",
    version="1.0.0",
    author="VPS Dev Agent",
    description="Autonomous AI development agent for VPS with PARA knowledge management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/vps-dev-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "agent=vps_dev_agent.cli.main:main",
        ],
    },
)
