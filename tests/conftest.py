import warnings
import pytest

@pytest.fixture(autouse=True)
def ignore_pydantic_warnings():
    warnings.filterwarnings(
        "ignore",
        message="Support for class-based.*",
        category=DeprecationWarning
    ) 