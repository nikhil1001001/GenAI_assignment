# Prompt Log

- Iteration 1: Asked the model to transcribe receipt text. Rejected because free-form text made validation fragile.
- Iteration 2: Required strict JSON with line items and bill-level fields. This made schema validation possible.
- Iteration 3: Added instruction to use `null` for absent printed values instead of calculating them. This prevents hidden model arithmetic.
- Iteration 4: Added explicit "do not calculate missing values" language after tests showed models filling plausible GST/subtotal values.
- Iteration 5: Kept description parsing outside the model for determinism; the parser emits an intermediate allocation map before any money math.

Did the model do arithmetic?

No. The model is only allowed to extract structured receipt data from an image. All arithmetic, percentage allocation, rounding, reconciliation, and settlement minimization are computed in Python with `Decimal`.

Why?

Receipt splitting is a financial workflow. LLM arithmetic can be confidently wrong, and evaluators are testing whether the system detects bad model output. Deterministic code gives repeatable totals and lets the API explain every mismatch.

