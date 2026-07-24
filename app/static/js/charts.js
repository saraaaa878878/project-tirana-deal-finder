/* charts.js — renders the three analytics charts from window.MARKET_STATS */
(function () {
  const S = window.MARKET_STATS;
  if (!S || typeof Chart === "undefined") return;

  // Identity colours
  const LINE = "#E2E0D8", MUTED = "#87897F";
  const BRAND = "#16412F", GREAT = "#1E6E4E", GOOD = "#B07D24", BAD = "#8A8C82";

  Chart.defaults.font.family = "'Schibsted Grotesk', system-ui, sans-serif";
  Chart.defaults.color = MUTED;

  // Shared options for the two bar charts.
  function barOptions(isEuro) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: isEuro
            ? { label: (c) => "\u20ac" + c.parsed.y.toLocaleString() }
            : { label: (c) => c.parsed.y.toLocaleString() + " listings" },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
        y: {
          grid: { color: LINE },
          beginAtZero: true,
          ticks: isEuro ? { callback: (v) => "\u20ac" + v / 1000 + "k" } : {},
        },
      },
    };
  }

  // 1. Price distribution
  new Chart(document.getElementById("chartDistribution"), {
    type: "bar",
    data: {
      labels: S.distribution.map((d) => d.label),
      datasets: [{ data: S.distribution.map((d) => d.count), backgroundColor: BRAND, borderRadius: 4 }],
    },
    options: barOptions(false),
  });

  // 2. Median price by bedrooms
  new Chart(document.getElementById("chartBedrooms"), {
    type: "bar",
    data: {
      labels: S.by_bedrooms.map((d) => d.bedrooms + " bd"),
      datasets: [{ data: S.by_bedrooms.map((d) => d.median_price), backgroundColor: GREAT, borderRadius: 4 }],
    },
    options: barOptions(true),
  });

  // 3. Deal breakdown (doughnut) — the hero feature, summarised
  new Chart(document.getElementById("chartGrades"), {
    type: "doughnut",
    data: {
      labels: ["Great deals", "Good deals", "Market price"],
      datasets: [{
        data: [S.by_grade.great, S.by_grade.good, S.by_grade.bad],
        backgroundColor: [GREAT, GOOD, BAD],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: { legend: { position: "bottom", labels: { padding: 16, usePointStyle: true } } },
    },
  });
})();
