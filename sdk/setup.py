from setuptools import setup, find_packages

setup(
    name="evalyx",
    version="0.1.0",
    description="Python SDK for the Evalyx LLM tracing platform",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "httpx>=0.24.0",
    ],
    extras_require={
        "openai": ["openai>=1.0.0"],
        "anthropic": ["anthropic>=0.18.0"],
        "langchain": ["langchain>=0.1.0"],
    },
)
