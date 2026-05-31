from __future__ import annotations

import re
from collections import OrderedDict

from fair_split.models import ParsedDescription, Receipt


STOP_NAMES = {
    "I",
    "We",
    "The",
    "Everything",
    "A",
    "An",
    "All",
    "Rest",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
}


ALIASES = {
    "pasta": ["pasta", "penne", "arrabiata"],
    "lime soda": ["lime soda", "fresh lime"],
    "sandwich": ["sandwich"],
    "brownie": ["brownie"],
    "cappuccino": ["cappuccino"],
    "pizza": ["pizza", "margherita"],
    "beer": ["beer"],
    "beers": ["beer"],
    "mojito": ["mojito"],
    "garlic bread": ["garlic bread"],
    "gulab jamun": ["gulab jamun", "jamun"],
    "chicken biryani": ["chicken biryani"],
    "veg biryani": ["veg biryani"],
    "rogan josh": ["rogan", "rogan josh", "mutton"],
    "raita": ["raita"],
    "soft drinks": ["soft drink", "soft drinks"],
}


def parse_description(description: str, receipt: Receipt) -> ParsedDescription:
    safe_description = (description or "")[:5000]
    flags: list[str] = []
    assumptions: list[str] = []
    if len(description or "") > 5000:
        flags.append("Description was truncated at 5000 characters")

    participants = _extract_participants(safe_description, receipt)
    paid_by = _extract_payer(safe_description, participants)
    if not paid_by:
        flags.append("No payer was stated in the description")
    elif paid_by not in participants:
        participants.append(paid_by)
        assumptions.append(f"Added payer {paid_by} to participant list")

    allocations: dict[str, list[str]] = {}
    sentences = _sentences(safe_description)
    for sentence in sentences:
        lowered = sentence.lower()
        if "paid" in lowered:
            continue
        matched_items = _items_mentioned(sentence, receipt)
        if not matched_items and _everything_else(lowered):
            matched_items = [item.name for item in receipt.items if item.name not in allocations]
        if not matched_items:
            continue
        consumers = _consumers_for_sentence(sentence, participants)
        if _everything_else(lowered):
            assumptions.append(
                f"Interpreted 'everything else' as {', '.join(matched_items)}"
            )
        if _rest_clause(lowered):
            assumptions.append(
                f"Interpreted 'rest of us' as {', '.join(consumers) if consumers else 'unknown'}"
            )
        if consumers:
            for item in matched_items:
                allocations[item] = consumers
        else:
            flags.append(f"Could not identify consumers for: {sentence}")

    for item in receipt.items:
        if item.name not in allocations:
            flags.append(f"No allocation was found for receipt item '{item.name}'")

    mentioned_unknown = _unknown_food_mentions(safe_description, receipt)
    flags.extend(f"Description mentions item not found on bill: '{name}'" for name in mentioned_unknown)
    return ParsedDescription(participants, paid_by, allocations, assumptions, flags)


def _extract_participants(text: str, receipt: Receipt) -> list[str]:
    names: OrderedDict[str, None] = OrderedDict()
    roster_match = re.search(
        r"(?:of us|people|participants|friends)?\s*[:—-]\s*([A-Z][A-Za-z]*(?:\s*,\s*[A-Z][A-Za-z]*)*(?:\s+and\s+[A-Z][A-Za-z]*)?)",
        text,
    )
    if roster_match:
        for name in _names_from_fragment(roster_match.group(1)):
            names[name] = None
    item_words = {
        word
        for item in receipt.items
        for word in re.findall(r"\b[A-Z][a-z]{2,}\b", item.name)
    }
    for name in re.findall(r"\b[A-Z][a-z]{2,}\b", text):
        if (
            name not in STOP_NAMES
            and name not in item_words
            and name.lower() not in {"gst", "cgst", "sgst"}
        ):
            names[name] = None
    return list(names)


def _extract_payer(text: str, participants: list[str]) -> str | None:
    for pattern in [
        r"\b([A-Z][a-z]{2,})\s+paid\b",
        r"\bpaid\s+by\s+([A-Z][a-z]{2,})\b",
        r"\b([A-Z][a-z]{2,})\s+settled\b",
    ]:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    if re.search(r"\bI paid\b", text, re.I) and len(participants) == 1:
        return participants[0]
    return None


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.!?]\s+", text) if part.strip()]


def _items_mentioned(sentence: str, receipt: Receipt) -> list[str]:
    lowered = sentence.lower()
    found: list[str] = []
    for item in receipt.items:
        item_key = item.name.lower()
        candidates = [item_key]
        for alias, words in ALIASES.items():
            if alias in item_key:
                candidates.extend(words)
        if any(word in lowered for word in candidates):
            found.append(item.name)
    return found


def _consumers_for_sentence(sentence: str, participants: list[str]) -> list[str]:
    lowered = sentence.lower()
    explicit = [name for name in participants if re.search(rf"\b{re.escape(name)}\b", sentence)]
    if "all" in lowered or "common" in lowered or "everyone" in lowered:
        if "except" in lowered or "skipped" in lowered:
            skipped = [
                name
                for name in participants
                if re.search(rf"\b{re.escape(name)}\b.*\b(?:except|skipped)\b", sentence, re.I)
                or re.search(rf"\b(?:except|skipped)\b.*\b{re.escape(name)}\b", sentence, re.I)
            ]
            return [name for name in participants if name not in skipped]
        return participants[:]
    if "rest of us" in lowered or "everyone else" in lowered:
        return [name for name in participants if name not in explicit] or participants[:]
    if "shared" in lowered and explicit:
        return explicit
    if explicit:
        return explicit
    return []


def _everything_else(lowered: str) -> bool:
    return (
        "everything else" in lowered
        or "common to all" in lowered
        or "had everything" in lowered
        or "shared everything" in lowered
    )


def _rest_clause(lowered: str) -> bool:
    return "rest of us" in lowered or "everyone else" in lowered


def _names_from_fragment(fragment: str) -> list[str]:
    return re.findall(r"\b[A-Z][a-z]{2,}\b", fragment)


def _unknown_food_mentions(text: str, receipt: Receipt) -> list[str]:
    known = " ".join(item.name.lower() for item in receipt.items)
    candidates = re.findall(r"\b(?:the\s+)?([a-z][a-z ]{2,25})\b", text.lower())
    suspicious = []
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate in {"bill", "coupon", "all", "else", "common", "shared equally"}:
            continue
        if any(food in candidate for food in ["sushi", "taco", "burger"]) and candidate not in known:
            suspicious.append(candidate)
    return sorted(set(suspicious))
