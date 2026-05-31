from __future__ import annotations

from decimal import Decimal

from fair_split.models import PersonLedger


def settle(ledgers: list[PersonLedger], paid_by: str | None) -> list[dict[str, Decimal | str]]:
    if not paid_by:
        return []
    balances = {ledger.name: -ledger.total for ledger in ledgers}
    total_paid = sum((ledger.total for ledger in ledgers), Decimal("0"))
    balances[paid_by] = balances.get(paid_by, Decimal("0")) + total_paid

    debtors = sorted(
        [(name, -amount) for name, amount in balances.items() if amount < 0],
        key=lambda row: row[1],
        reverse=True,
    )
    creditors = sorted(
        [(name, amount) for name, amount in balances.items() if amount > 0],
        key=lambda row: row[1],
        reverse=True,
    )
    transfers: list[dict[str, Decimal | str]] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]
        amount = min(debt, credit)
        if amount > 0:
            transfers.append({"from": debtor, "to": creditor, "amount": amount})
        debtors[i] = (debtor, debt - amount)
        creditors[j] = (creditor, credit - amount)
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers

