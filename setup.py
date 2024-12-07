from setuptools import setup, find_packages

setup(
    name="ifc-service",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi==0.109.2",
        "python-multipart==0.0.9",
        "ifcopenshell==0.8.0",
        "uvicorn==0.27.1",
        "pydantic==2.5.3",
        "pydantic-settings==2.1.0"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "httpx",
            "black",
            "isort",
            "mypy",
            "flake8"
        ]
    }
) 