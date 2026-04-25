"""
Virtual wallet transaction model.
"""
from decimal import Decimal
import uuid

from sqlalchemy import Column, String, DECIMAL, DateTime
from sqlalchemy.sql import func

from app.database import Base


class WalletTransaction(Base):
    """Wallet transaction history for virtual coin changes."""

    __tablename__ = "wallet_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, comment="用户ID")
    transaction_type = Column(String(32), nullable=False, comment="流水类型")
    change_amount = Column(DECIMAL(10, 2), nullable=False, default=Decimal("0.00"), comment="变动金额")
    balance_after = Column(DECIMAL(10, 2), nullable=False, default=Decimal("0.00"), comment="变动后余额")
    related_order_id = Column(String(36), nullable=True, comment="关联订单ID")
    note = Column(String(255), nullable=True, comment="备注")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self) -> str:
        return (
            f"<WalletTransaction(id={self.id}, user_id={self.user_id}, "
            f"type={self.transaction_type}, amount={self.change_amount})>"
        )
