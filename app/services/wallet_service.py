"""
Virtual wallet helpers and service methods.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import WalletTransaction

DEFAULT_VIRTUAL_COIN_BALANCE = Decimal("200.00")
VIRTUAL_CURRENCY_NAME = "餐币"
VIRTUAL_CURRENCY_DISPLAY_NAME = "虚拟币"
PAYMENT_METHOD_FREE = "free"
PAYMENT_METHOD_WECHAT = "wechat"
PAYMENT_METHOD_VIRTUAL_COIN = "virtual_coin"
SUPPORTED_PAYMENT_METHODS = {PAYMENT_METHOD_WECHAT, PAYMENT_METHOD_VIRTUAL_COIN}


class WalletServiceError(Exception):
    """Wallet related exception."""

    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def normalize_decimal_amount(value: Decimal | int | float | str) -> Decimal:
    amount = Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    return amount


def get_user_wallet_balance(user: User) -> Decimal:
    balance = getattr(user, "virtual_coin_balance", None)
    if balance is None:
        user.virtual_coin_balance = DEFAULT_VIRTUAL_COIN_BALANCE
        return DEFAULT_VIRTUAL_COIN_BALANCE
    return normalize_decimal_amount(balance)


def build_wallet_payload(user: User) -> dict:
    balance = get_user_wallet_balance(user)
    return {
        "balance": float(balance),
        "currency_name": VIRTUAL_CURRENCY_NAME,
        "display_name": VIRTUAL_CURRENCY_DISPLAY_NAME,
        "exchange_rate": 1,
        "exchange_rate_text": f"1 {VIRTUAL_CURRENCY_NAME} = 1 元",
    }


def resolve_payment_method(value: Optional[str], total_price: Decimal | int | float | str) -> str:
    amount = normalize_decimal_amount(total_price)
    if amount <= Decimal("0.00"):
        return PAYMENT_METHOD_FREE

    normalized = (value or PAYMENT_METHOD_WECHAT).strip().lower()
    if normalized not in SUPPORTED_PAYMENT_METHODS:
        raise WalletServiceError("不支持的支付方式")
    return normalized


class WalletService:
    """Virtual wallet service."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_or_raise(self, user_id: str) -> User:
        user = self.db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
        if not user:
            raise WalletServiceError("用户不存在", code=404)
        return user

    def ensure_sufficient_balance(self, user: User, amount: Decimal | int | float | str) -> Decimal:
        normalized_amount = normalize_decimal_amount(amount)
        if normalized_amount <= Decimal("0.00"):
            return Decimal("0.00")

        balance = get_user_wallet_balance(user)
        if balance < normalized_amount:
            raise WalletServiceError(
                f"{VIRTUAL_CURRENCY_DISPLAY_NAME}余额不足，当前余额 {float(balance):.2f} {VIRTUAL_CURRENCY_NAME}",
                code=400,
            )
        return normalized_amount

    def add_balance(
        self,
        user: User,
        amount: Decimal | int | float | str,
        transaction_type: str,
        note: Optional[str] = None,
        related_order_id: Optional[str] = None,
    ) -> WalletTransaction:
        normalized_amount = normalize_decimal_amount(amount)
        if normalized_amount <= Decimal("0.00"):
            raise WalletServiceError("充值金额必须大于0")

        next_balance = get_user_wallet_balance(user) + normalized_amount
        user.virtual_coin_balance = next_balance

        transaction = WalletTransaction(
            user_id=user.id,
            transaction_type=transaction_type,
            change_amount=normalized_amount,
            balance_after=next_balance,
            related_order_id=related_order_id,
            note=note,
        )
        self.db.add(transaction)
        return transaction

    def deduct_balance(
        self,
        user: User,
        amount: Decimal | int | float | str,
        transaction_type: str,
        note: Optional[str] = None,
        related_order_id: Optional[str] = None,
    ) -> WalletTransaction:
        normalized_amount = self.ensure_sufficient_balance(user, amount)
        next_balance = get_user_wallet_balance(user) - normalized_amount
        user.virtual_coin_balance = next_balance

        transaction = WalletTransaction(
            user_id=user.id,
            transaction_type=transaction_type,
            change_amount=-normalized_amount,
            balance_after=next_balance,
            related_order_id=related_order_id,
            note=note,
        )
        self.db.add(transaction)
        return transaction

    def top_up(
        self,
        user_id: str,
        amount: Decimal | int | float | str,
        note: Optional[str] = None,
    ) -> Tuple[User, WalletTransaction]:
        user = self.get_user_or_raise(user_id)
        transaction = self.add_balance(
            user=user,
            amount=amount,
            transaction_type="topup",
            note=note or f"充值 {normalize_decimal_amount(amount):.2f} {VIRTUAL_CURRENCY_NAME}",
        )
        self.db.commit()
        self.db.refresh(user)
        self.db.refresh(transaction)
        return user, transaction

    def list_transactions(self, user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[WalletTransaction], int]:
        query = self.db.query(WalletTransaction).filter(WalletTransaction.user_id == user_id)
        total = query.count()
        items = (
            query.order_by(WalletTransaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total
