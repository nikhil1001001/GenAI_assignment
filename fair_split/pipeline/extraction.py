from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

from fair_split.models import Receipt, ReceiptItem, money

LOGGER = logging.getLogger(__name__)


RECEIPT_SCHEMA_HINT = {
    "items": [{"name": "string", "qty": "number", "amount": "number"}],
    "subtotal": "number|null",
    "service_charge": "number",
    "tax": "number",
    "discount": "number",
    "tip": "number",
    "extra_fees": "number",
    "grand_total": "number|null",
}


class ExtractionError(ValueError):
    pass


def extract_receipt(receipt_base64: str) -> tuple[Receipt | None, list[str]]:
    """Extract a receipt into a strict structure.

    The preferred path is an LLM vision extractor configured by OPENAI_API_KEY.
    For tests and local development, UTF-8 text or JSON encoded as base64 is
    also accepted. Arithmetic is deliberately not trusted here.
    """
    flags: list[str] = []
    try:
        payload = base64.b64decode(receipt_base64, validate=True)
    except (binascii.Error, ValueError):
        return None, ["receipt_base64 is not valid base64"]

    if len(payload) > 8_000_000:
        return None, ["receipt image exceeds 8 MB limit"]

    text = _try_decode_text(payload)
    if text:
        try:
            return _receipt_from_json_or_text(text), flags
        except ExtractionError as exc:
            flags.append(str(exc))

    if os.getenv("OPENAI_API_KEY"):
        try:
            return _extract_with_openai(receipt_base64), flags
        except ExtractionError as exc:
            LOGGER.warning("receipt_extraction_failed", extra={"reason": str(exc)})
            return None, [f"Receipt extraction failed: {exc}"]

    return None, [
        "No local OCR engine or OPENAI_API_KEY is configured; receipt could not be read"
    ]


def _try_decode_text(payload: bytes) -> str | None:
    if payload.startswith(b"\x89PNG") or payload.startswith(b"\xff\xd8"):
        return None
    try:
        text = payload.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    return text if text else None


def _receipt_from_json_or_text(text: str) -> Receipt:
    if text.lstrip().startswith("{"):
        data = json.loads(text)
        return _coerce_receipt(data, raw_text=text)
    return _parse_plaintext_receipt(text)


def _extract_with_openai(receipt_base64: str) -> Receipt:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    mime = _guess_mime(receipt_base64)
    prompt = (
        "Extract this restaurant bill as JSON only. Do not calculate missing "
        "values. Use null when a printed value is absent. Required shape: "
        f"{json.dumps(RECEIPT_SCHEMA_HINT)}"
    )
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime};base64,{receipt_base64}",
                    },
                ],
            }
        ],
        "text": {"format": {"type": "json_object"}},
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ExtractionError(str(exc)) from exc

    text = _openai_text(raw)
    if not text:
        raise ExtractionError("model returned no JSON text")
    try:
        return _coerce_receipt(json.loads(text), raw_text=text)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ExtractionError(f"invalid model JSON: {exc}") from exc


def _openai_text(raw: dict[str, Any]) -> str:
    if isinstance(raw.get("output_text"), str):
        return raw["output_text"]
    chunks: list[str] = []
    for item in raw.get("output", []):
        for part in item.get("content", []):
            if part.get("type") in {"output_text", "text"} and part.get("text"):
                chunks.append(part["text"])
    return "".join(chunks).strip()


def _guess_mime(receipt_base64: str) -> str:
    head = base64.b64decode(receipt_base64[:24] + "===")
    if head.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    return "image/jpeg"


def _coerce_receipt(data: dict[str, Any], raw_text: str = "") -> Receipt:
    if not isinstance(data.get("items"), list):
        raise ExtractionError("receipt JSON must include an items array")
    items = []
    for item in data["items"]:
        if not item.get("name"):
            raise ExtractionError("receipt item is missing a name")
        amount = money(item.get("amount"))
        qty = money(item.get("qty", 1))
        if amount < 0 or qty <= 0:
            raise ExtractionError(f"invalid line item value for {item.get('name')}")
        items.append(ReceiptItem(str(item["name"]).strip(), amount, qty))
    return Receipt(
        items=items,
        subtotal=_nullable_money(data.get("subtotal")),
        service_charge=money(data.get("service_charge")),
        tax=money(data.get("tax")),
        discount=money(data.get("discount")),
        tip=money(data.get("tip")),
        extra_fees=money(data.get("extra_fees")),
        grand_total=_nullable_money(data.get("grand_total")),
        raw_text=raw_text,
    )


def _nullable_money(value: Any) -> Decimal | None:
    return None if value is None else money(value)


def _parse_plaintext_receipt(text: str) -> Receipt:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items: list[ReceiptItem] = []
    subtotal = service = tax = discount = tip = fees = grand_total = None
    for line in lines:
        label, value = _split_label_amount(line)
        if value is None:
            continue
        key = label.lower()
        if "subtotal" in key:
            subtotal = value
        elif "service" in key:
            service = value
        elif "gst" in key or "tax" in key or "cgst" in key or "sgst" in key:
            tax = (tax or Decimal("0")) + value
        elif "discount" in key or "coupon" in key:
            discount = -abs(value)
        elif "tip" in key:
            tip = value
        elif "fee" in key or "charge" in key:
            fees = value
        elif "grand" in key or "total" == key:
            grand_total = value
        elif not any(word in key for word in ["round", "bill", "date"]):
            qty_match = re.search(r"\bqty\s*(\d+(?:\.\d+)?)\b", key)
            qty = money(qty_match.group(1)) if qty_match else Decimal("1")
            clean_label = re.sub(r"\bqty\s*\d+(?:\.\d+)?\b", "", label, flags=re.I)
            items.append(ReceiptItem(clean_label.strip(" :-"), value, qty))
    if not items:
        raise ExtractionError("no receipt line items found")
    return Receipt(
        items=items,
        subtotal=subtotal,
        service_charge=service or Decimal("0"),
        tax=tax or Decimal("0"),
        discount=discount or Decimal("0"),
        tip=tip or Decimal("0"),
        extra_fees=fees or Decimal("0"),
        grand_total=grand_total,
        raw_text=text,
    )


def _split_label_amount(line: str) -> tuple[str, Decimal | None]:
    match = re.search(r"(.+?)[\s:,-]+(?:₹|rs\.?)?\s*(-?\d+(?:\.\d+)?)\s*$", line, re.I)
    if not match:
        return line, None
    return match.group(1).strip(), money(match.group(2))

