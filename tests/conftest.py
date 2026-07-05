from pathlib import Path
import pytest

FIX = Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_cv_text() -> str:
    return (FIX / "sample_cv.txt").read_text(encoding="utf-8")

@pytest.fixture
def sample_offer_text() -> str:
    return (FIX / "sample_offer.txt").read_text(encoding="utf-8")
