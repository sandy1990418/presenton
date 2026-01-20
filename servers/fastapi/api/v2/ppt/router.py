"""V2 PPT API Router"""

from fastapi import APIRouter

from api.v2.ppt.stateless import STATELESS_ROUTER


API_V2_PPT_ROUTER = APIRouter(prefix="/api/v2/ppt")

API_V2_PPT_ROUTER.include_router(STATELESS_ROUTER)
