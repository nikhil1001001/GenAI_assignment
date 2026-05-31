# Edge Cases

| Edge case | Input shape | Handling | Verified |
| --- | --- | --- | --- |
| Receipt unreadable | Invalid base64 or image with no OCR provider | Return contract with flag, no guessed split | Yes |
| Missing payer | Description has names/items but no "paid" phrase | Flag missing payer; no settlement | Yes |
| Duplicate items | Repeated item names in receipt JSON | Kept as separate line items; ambiguous description may flag unallocated rows | Partially |
| Item not found | Description mentions unrelated food such as sushi | Flag unknown item mention | Partially |
| Missing subtotal | `subtotal: null` | Use sum of line items and flag missing subtotal | Yes |
| Missing tax | `tax: 0` or absent field | Treat as zero after schema coercion | Yes |
| No service charge | `service_charge: 0` | Allocate zero service charge | Yes |
| Discount mismatch | Components do not add to grand total | Flag arithmetic mismatch | Yes |
| Tip present | `tip` field present | Allocate with tax/extra charges proportionally | Yes |
| Extra fees | `extra_fees` field present | Allocate proportionally and reconcile | Yes |
| Negative values | Negative non-discount field | Flag as invalid/negative | Yes |
| OCR price error | Item sum differs from subtotal | Flag line-item/subtotal mismatch | Yes |
| OCR quantity error | Quantity impossible or zero | Reject extraction | Yes |
| Large group | 10+ names in description | Parser keeps participant list; settlement remains minimized | Partially |
| Shared subset | "shared just by Priya and Karan" | Allocate item only to named subset | Yes |
| Uneven quantities | Quantity and amount on line item | Split amount by consumers, not by guessed units | Yes |
| Receipt total mismatch | Printed total differs from components | Flag mismatch, reconcile to printed grand total | Yes |
| Missing grand total | `grand_total: null` | Use computed total and flag missing grand total | Yes |
| Missing item prices | Item amount missing/null | Coerces to zero and validation catches subtotal mismatch | Partially |
| Participant not referenced | Named participant consumes no items | Included with zero total if named | Yes |
| Everything else clause | "Everything else common to all" | Allocate all still-unallocated items to all participants; record assumption | Yes |
| Rest of us clause | "everyone else" / "rest of us" | Interpret as all participants not explicitly named; record assumption | Partially |
| Multiple discounts | Combined into one bill-level discount by extractor | Allocated proportionally | Partially |
| Floating precision | Paise and fractional shares | Use `Decimal`, round only at output, assign residual | Yes |
| Prompt injection | Receipt/description contains instructions | Treated as data; model prompt only asks for JSON; calculations ignore instructions | Partially |
| Extremely long description | >5000 characters | Truncate and flag | Yes |

