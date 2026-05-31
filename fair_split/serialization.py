from __future__ import annotations

from decimal import Decimal
from typing import Any

from fair_split.models import PipelineResult


def result_to_contract(result: PipelineResult) -> dict[str, Any]:
    return {
        "per_person": [
            {
                "name": ledger.name,
                "items": ledger.item_labels,
                "subtotal": _number(ledger.subtotal),
                "tax_share": _number(ledger.tax_share),
                "service_share": _number(ledger.service_share),
                "discount_share": _number(ledger.discount_share),
                "total": _number(ledger.total),
            }
            for ledger in result.per_person
        ],
        "grand_total": _number(result.grand_total),
        "reconciliation": {
            "sum_of_person_totals": _number(result.sum_of_person_totals),
            "matches_bill": result.matches_bill,
        },
        "paid_by": result.paid_by,
        "settle_up": [
            {"from": row["from"], "to": row["to"], "amount": _number(row["amount"])}
            for row in result.settle_up
        ],
        "assumptions": result.assumptions,
        "flags": result.flags,
    }


def _number(value: Decimal | str) -> int | float | str:
    if not isinstance(value, Decimal):
        return value
    if value == value.to_integral_value():
        return int(value)
    return float(value)

