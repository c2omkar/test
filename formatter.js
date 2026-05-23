function formatCurrency(amount, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
}

function formatDate(date) {
  return new Intl.DateTimeFormat("en-US").format(new Date(date));
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

module.exports = { formatCurrency, formatDate, formatPercent };
