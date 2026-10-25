from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.integrations import model_client
from app.models import User
from app.schemas.search import SearchQuery, SearchRequest, SearchResult
from app.services.dates import today_local
from app.services.retrieval import RetrievalService

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResult)
async def search(
    body: SearchRequest, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> SearchResult:
    query = SearchQuery(question=body.question, from_date=body.from_date, to_date=body.to_date)
    return await RetrievalService(db, model_client.get_model_client()).search(user.id, query, today_local())
