from fastapi import APIRouter, HTTPException
from services.auction_service import AuctionService

router = APIRouter(prefix="/api/auctions", tags=["Auctions"])
service = AuctionService()

@router.get("/")
def get_auctions():
    return service.get_all_auctions()

@router.get("/stats")
def get_stats():
    return service.get_stats()
