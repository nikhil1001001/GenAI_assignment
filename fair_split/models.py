from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


Money = Decimal


def money(value: Any) -> Money:
    return Decimal(str(value or 0))


@dataclass(frozen=True)
class ReceiptItem:
    name: str
    amount: Money
    qty: Money = Decimal("1")


@dataclass(frozen=True)
class Receipt:
    items: list[ReceiptItem]
    subtotal: Money | None = None
    service_charge: Money = Decimal("0")
    tax: Money = Decimal("0")
    discount: Money = Decimal("0")
    tip: Money = Decimal("0")
    extra_fees: Money = Decimal("0")
    grand_total: Money | None = None
    raw_text: str = ""


@dataclass
class ParsedDescription:
    participants: list[str]
    paid_by: str | None
    allocations: dict[str, list[str]]
    assumptions: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


@dataclass
class PersonLedger:
    name: str
    item_labels: list[str]
    subtotal: Money
    tax_share: Money
    service_share: Money
    discount_share: Money
    total: Money


@dataclass
class PipelineResult:
    per_person: list[PersonLedger]
    grand_total: Money
    sum_of_person_totals: Money
    matches_bill: bool
    paid_by: str | None
    settle_up: list[dict[str, Money | str]]
    assumptions: list[str]
    flags: list[str]

