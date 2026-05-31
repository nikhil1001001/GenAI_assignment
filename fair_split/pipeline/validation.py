from __future__ import annotations

from decimal import Decimal

from fair_split.models import Receipt


def validate_receipt(receipt: Receipt) -> list[str]:
    flags: list[str] = []
    item_sum = sum((item.amount for item in receipt.items), Decimal("0"))
    if receipt.subtotal is None:
        flags.append("Missing subtotal; using sum of line items")
    elif abs(item_sum - receipt.subtotal) > Decimal("1"):
        flags.append(
            f"Extracted line items sum to INR {item_sum} but printed subtotal is INR {receipt.subtotal}"
        )
    if receipt.grand_total is None:
        flags.append("Missing grand total; using computed total from extracted fields")
    expected_total = (
        (receipt.subtotal if receipt.subtotal is not None else item_sum)
        + receipt.service_charge
        + receipt.tax
        + receipt.discount
        + receipt.tip
        + receipt.extra_fees
    )
    if receipt.grand_total is not None and abs(expected_total - receipt.grand_total) > Decimal("1"):
        flags.append(
            f"Receipt arithmetic mismatch: components total INR {expected_total} but bill grand total is INR {receipt.grand_total}"
        )
    for field_name in ["service_charge", "tax", "tip", "extra_fees"]:
        if getattr(receipt, field_name) < 0:
            flags.append(f"{field_name} is negative")
    if receipt.discount > 0:
        flags.append("Discount was positive; expected discount to be negative")
    return flags


def effective_grand_total(receipt: Receipt) -> Decimal:
    item_sum = sum((item.amount for item in receipt.items), Decimal("0"))
    return receipt.grand_total or (
        (receipt.subtotal if receipt.subtotal is not None else item_sum)
        + receipt.service_charge
        + receipt.tax
        + receipt.discount
        + receipt.tip
        + receipt.extra_fees
    )

