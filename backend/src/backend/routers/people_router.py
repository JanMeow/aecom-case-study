"""Staff directory."""
from fastapi import APIRouter

from backend.ETL.extraction import load_staff
from backend.ETL.model import Owner

router = APIRouter(prefix="/people", tags=["people"])


@router.get("")
def list_people() -> list[Owner]:
    """Staff directory, for the logged-in user switcher."""
    return load_staff()
