from __future__ import annotations

import logging
from decimal import Decimal

from fair_split.models import PipelineResult
from fair_split.pipeline.calculation import allocate_and_calculate
from fair_split.pipeline.description import parse_description
from fair_split.pipeline.extraction import extract_receipt
from fair_split.pipeline.settlement import settle
from fair_split.pipeline.validation import effective_grand_total, validate_receipt

LOGGER = logging.getLogger(__name__)


def split_bill(receipt_base64: str, description: str) -> PipelineResult:
    assumptions: list[str] = []
    flags: list[str] = []

    receipt, extraction_flags = extract_receipt(receipt_base64)
    flags.extend(extraction_flags)
    if receipt is None:
        return PipelineResult([], Decimal("0"), Decimal("0"), False, None, [], assumptions, flags)

    receipt_flags = validate_receipt(receipt)
    flags.extend(receipt_flags)
    if receipt_flags:
        LOGGER.info("receipt_validation_flags", extra={"count": len(receipt_flags)})

    parsed = parse_description(description, receipt)
    assumptions.extend(parsed.assumptions)
    flags.extend(parsed.flags)

    ledgers, calc_assumptions, calc_flags = allocate_and_calculate(receipt, parsed)
    assumptions.extend(calc_assumptions)
    flags.extend(calc_flags)

    grand_total = effective_grand_total(receipt).quantize(Decimal("1"))
    sum_totals = sum((ledger.total for ledger in ledgers), Decimal("0"))
    matches = sum_totals == grand_total
    if not matches:
        flags.append(
            f"Reconciliation failed: person totals INR {sum_totals} but bill total INR {grand_total}"
        )
        LOGGER.warning("reconciliation_failed")

    return PipelineResult(
        per_person=ledgers,
        grand_total=grand_total,
        sum_of_person_totals=sum_totals,
        matches_bill=matches,
        paid_by=parsed.paid_by,
        settle_up=settle(ledgers, parsed.paid_by),
        assumptions=assumptions,
        flags=flags,
    )

