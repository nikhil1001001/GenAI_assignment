from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext

from fair_split.models import ParsedDescription, PersonLedger, Receipt
from fair_split.pipeline.validation import effective_grand_total

getcontext().prec = 28


def allocate_and_calculate(
    receipt: Receipt, parsed: ParsedDescription
) -> tuple[list[PersonLedger], list[str], list[str]]:
    assumptions: list[str] = []
    flags: list[str] = []
    participants = parsed.participants
    raw_subtotals = {name: Decimal("0") for name in participants}
    labels = {name: [] for name in participants}

    for item in receipt.items:
        consumers = parsed.allocations.get(item.name)
        if not consumers:
            continue
        share = item.amount / Decimal(len(consumers))
        for consumer in consumers:
            raw_subtotals.setdefault(consumer, Decimal("0"))
            labels.setdefault(consumer, [])
            raw_subtotals[consumer] += share
            labels[consumer].append(_item_label(item.name, len(consumers), len(participants)))

    subtotal_base = sum(raw_subtotals.values(), Decimal("0"))
    if subtotal_base == 0:
        flags.append("No allocatable subtotal found")
        return [], assumptions, flags

    service_raw = _proportional(raw_subtotals, receipt.service_charge, subtotal_base)
    tax_raw = _proportional(raw_subtotals, receipt.tax + receipt.tip + receipt.extra_fees, subtotal_base)
    discount_raw = _proportional(raw_subtotals, receipt.discount, subtotal_base)
    grand_total = effective_grand_total(receipt)
    raw_totals = {
        name: raw_subtotals[name] + service_raw[name] + tax_raw[name] + discount_raw[name]
        for name in raw_subtotals
    }
    rounded_totals, residual_assumption = _round_with_residual(raw_totals, grand_total, parsed.paid_by)
    assumptions.append(residual_assumption)

    ledgers: list[PersonLedger] = []
    for name in participants:
        total = rounded_totals.get(name, Decimal("0"))
        subtotal_r = _rupee(raw_subtotals.get(name, Decimal("0")))
        service_r = _rupee(service_raw.get(name, Decimal("0")))
        tax_r = _rupee(tax_raw.get(name, Decimal("0")))
        discount_r = total - subtotal_r - service_r - tax_r
        ledgers.append(
            PersonLedger(
                name=name,
                item_labels=labels.get(name, []),
                subtotal=subtotal_r,
                tax_share=tax_r,
                service_share=service_r,
                discount_share=discount_r,
                total=total,
            )
        )
    return ledgers, assumptions, flags


def _proportional(
    subtotals: dict[str, Decimal], amount: Decimal, base: Decimal
) -> dict[str, Decimal]:
    return {name: amount * subtotal / base for name, subtotal in subtotals.items()}


def _round_with_residual(
    raw_totals: dict[str, Decimal], grand_total: Decimal, paid_by: str | None
) -> tuple[dict[str, Decimal], str]:
    rounded = {name: _rupee(total) for name, total in raw_totals.items()}
    target = _rupee(grand_total)
    residual = target - sum(rounded.values(), Decimal("0"))
    absorber = paid_by if paid_by in rounded else max(rounded, key=lambda name: raw_totals[name])
    rounded[absorber] += residual
    return rounded, f"Rounding residual of INR {residual} assigned to {absorber}"


def _rupee(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _item_label(name: str, consumers: int, participants: int) -> str:
    if consumers == 1:
        return name
    if consumers == 2:
        suffix = "1/2"
    elif consumers == participants:
        suffix = f"1/{participants}"
    else:
        suffix = f"1/{consumers}"
    return f"{name} ({suffix})"

