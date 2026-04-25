"""
Wallet API endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.common import paginated_response, success_response, error_response
from app.schemas.wallet import WalletTopUpRequest
from app.services.wallet_service import WalletService, WalletServiceError, build_wallet_payload


router = APIRouter(prefix="/wallet", tags=["钱包"])


@router.get("/profile")
async def get_wallet_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current user's wallet profile."""
    return success_response(data=build_wallet_payload(current_user))


@router.get("/transactions")
async def get_wallet_transactions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List wallet transactions."""
    service = WalletService(db)
    items, total = service.list_transactions(current_user.id, page=page, page_size=page_size)
    data = [
        {
            "id": item.id,
            "transaction_type": item.transaction_type,
            "change_amount": float(item.change_amount),
            "balance_after": float(item.balance_after),
            "related_order_id": item.related_order_id,
            "note": item.note,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]
    return paginated_response(data=data, page=page, page_size=page_size, total=total)


@router.post("/topup")
async def top_up_wallet(
    request: WalletTopUpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Top up wallet balance for dev/MVP usage."""
    service = WalletService(db)
    try:
        user, transaction = service.top_up(
            user_id=current_user.id,
            amount=request.amount,
            note=request.note,
        )
        return success_response(
            data={
                "wallet": build_wallet_payload(user),
                "transaction": {
                    "id": transaction.id,
                    "transaction_type": transaction.transaction_type,
                    "change_amount": float(transaction.change_amount),
                    "balance_after": float(transaction.balance_after),
                    "related_order_id": transaction.related_order_id,
                    "note": transaction.note,
                    "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
                },
            },
            message="虚拟币充值成功"
        )
    except WalletServiceError as e:
        return error_response(e.code, e.message)
