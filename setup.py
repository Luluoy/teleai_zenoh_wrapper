from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent.resolve()

setup(
    name="teleai-zenoh-wrapper",
    version="0.1.0",
    description="基于 Zenoh 的多机器人通信框架，提供 PubSub、RPC 及数据管理功能",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    license="MIT",
    python_requires=">=3.10",

    author="Luluoy",

    url="https://github.com/Luluoy/teleai-zenoh-wrapper",
    project_urls={
        "Homepage": "https://github.com/Luluoy/teleai-zenoh-wrapper",
        "Repository": "https://github.com/Luluoy/teleai-zenoh-wrapper",
        "Issues": "https://github.com/Luluoy/teleai-zenoh-wrapper/issues",
    },

    # 包发现：与 pyproject 里的 [tool.setuptools.packages.find] where=["src"] 对应
    packages=find_packages(where="src"),
    package_dir={"": "src"},

    install_requires=[
        "numpy<=2.0",
        "typing_extensions==4.15.0",
        "eclipse-zenoh==1.7.2",
        "colorlog<=6.10.1",
        "psutil>=5.9",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0",
            "pytest-cov>=6.0",
            "ruff>=0.11",
        ],
        "transfer": [
            "paramiko>=3.5",
            "h5py>=3.12",
        ],
    },

    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)