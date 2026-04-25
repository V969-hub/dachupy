"""
Wallet related schemas.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WalletInfo(BaseModel):
    balance: float
    currency_name: str
    display_name: str
    exchange_rate: int
    exchange_rate_text: str


class WalletTopUpRequest(BaseModel):
    amount: float = Field(..., gt=0, le=10000, description="充值金额")
    note: Optional[str] = Field(None, max_length=255, description="备注")


class WalletTransactionResponse(BaseModel):
    id: str
    transaction_type: str
    change_amount: float
    balance_after: float
    related_order_id: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
