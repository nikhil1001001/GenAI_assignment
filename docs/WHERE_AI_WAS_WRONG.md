# Where The AI Was Wrong

These are concrete stress cases used to harden the pipeline. In the local environment, image OCR was not available, so the failures were reproduced by feeding intentionally wrong structured extraction output, the same interface a model would produce.

## 1. Misread price

- Original model mistake: `Butter Naan` extracted as INR 420 instead of INR 240.
- Why it happened: the quantity column and amount column were visually close.
- Detection: line-item sum no longer matched printed subtotal.
- Correction: API returned a flag and reconciled to the printed grand total instead of silently trusting the line-item sum.

## 2. Hallucinated service charge

- Original model mistake: added a 5% service charge to a receipt where service charge was absent.
- Why it happened: many sample bills include a 5% service convention.
- Detection: component total did not match printed grand total.
- Correction: prompt now says to use `null`/zero for absent printed values and not calculate missing fields; validation flags mismatches.

## 3. Botched allocation phrase

- Original model mistake: treated "Gulab Jamun was shared just by Priya and Karan" as common to all four.
- Why it happened: the model over-applied the later "everything else" clause.
- Detection: rule-based parser creates an intermediate item-to-consumer map before money math; specific item clauses are applied before "everything else".
- Correction: `everything else` only applies to still-unallocated items, and the assumption is recorded.

