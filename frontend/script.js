const form = document.querySelector("#split-form");
const receipt = document.querySelector("#receipt");
const description = document.querySelector("#description");
const results = document.querySelector("#results");
const people = document.querySelector("#people");
const settle = document.querySelector("#settle");
const assumptions = document.querySelector("#assumptions");
const flags = document.querySelector("#flags");
const summary = document.querySelector("#summary");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  button.textContent = "Splitting...";
  try {
    const receipt_base64 = await toBase64(receipt.files[0]);
    const response = await fetch("/split", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ receipt_base64, description: description.value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed");
    render(data);
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Split bill";
  }
});

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.readAsDataURL(file);
  });
}

function render(data) {
  results.hidden = false;
  summary.innerHTML = `
    <span>Grand total: INR ${data.grand_total}</span>
    <span>Person totals: INR ${data.reconciliation.sum_of_person_totals}</span>
    <span>${data.reconciliation.matches_bill ? "Reconciled" : "Needs review"}</span>
    <span>Paid by: ${data.paid_by || "Not stated"}</span>
  `;
  people.innerHTML = data.per_person
    .map(
      (person) => `<tr>
        <td>${escapeHtml(person.name)}</td>
        <td>${person.items.map(escapeHtml).join("<br>")}</td>
        <td>${person.subtotal}</td>
        <td>${person.tax_share}</td>
        <td>${person.service_share}</td>
        <td>${person.discount_share}</td>
        <td><strong>${person.total}</strong></td>
      </tr>`
    )
    .join("");
  renderList(settle, data.settle_up.map((row) => `${row.from} pays ${row.to} INR ${row.amount}`));
  renderList(assumptions, data.assumptions);
  renderList(flags, data.flags.length ? data.flags : ["No flags"]);
}

function renderList(node, rows) {
  node.innerHTML = rows.map((row) => `<li>${escapeHtml(row)}</li>`).join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

