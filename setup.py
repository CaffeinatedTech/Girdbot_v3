from setuptools import setup, find_packages

setup(
    name="gridbot",
    version="3.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "ccxt==4.1.83",
        "websockets==12.0",
        "python-dotenv==1.0.0",
        "pydantic==2.5.2",
    ],
    extras_require={
        "dev": [
            "pytest==7.4.3",
            "pytest-asyncio==0.23.2",
            "pytest-mock==3.12.0",
            "aiohttp==3.9.1",
        ],
    },
    python_requires=">=3.8",
)
