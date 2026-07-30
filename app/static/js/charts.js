(function () {
  const S = window.MARKET_STATS;
  if (!S || typeof Chart === "undefined") return;
  const muted = "#9b9b97", grid = "rgba(255,255,255,.12)";
  const colors = { cityBlue: "#7895b5", blush: "#f3a4bc", yellow: "#f2b33d", pink: "#ff4f87" };
  Chart.defaults.font.family = "'Manrope', system-ui, sans-serif";
  Chart.defaults.color = muted;
  let signalChart;
  const gradient = (ctx, color) => { const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, ctx.chart.height); g.addColorStop(0, color); g.addColorStop(1, "rgba(8,14,29,0)"); return g; };
  function renderSignal(mode) {
    const beds = mode === "bedrooms", source = beds ? S.by_bedrooms : S.distribution;
    const labels = source.map(d => beds ? d.bedrooms + (window.MARKET_LANG === "sq" ? " dh" : " bd") : d.label);
    const values = source.map(d => beds ? d.median_price : d.count);
    const peak = values.indexOf(Math.max(...values));
    document.getElementById("signalLabel").textContent = window.MARKET_LANG === "sq"
      ? (beds ? "MEDIANA MË E LARTË" : "INTERVALI MË AKTIV")
      : (beds ? "HIGHEST MEDIAN" : "MOST ACTIVE RANGE");
    document.getElementById("signalValue").textContent = beds ? "€" + values[peak].toLocaleString() : labels[peak];
    if (signalChart) signalChart.destroy();
    signalChart = new Chart(document.getElementById("chartDistribution"), { type: "line", data: { labels, datasets: [{ data: values, borderColor: beds ? colors.blush : colors.pink, borderWidth: 3, tension: .42, fill: true, pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: "#171715", pointBorderColor: beds ? colors.blush : colors.pink, pointBorderWidth: 2, backgroundColor: ctx => gradient(ctx, beds ? "rgba(243,164,188,.25)" : "rgba(255,79,135,.28)") }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { displayColors: false, backgroundColor: "#f2efe8", titleColor: "#171715", bodyColor: "#55554f", padding: 14, callbacks: { label: c => beds ? "€" + c.parsed.y.toLocaleString() : c.parsed.y.toLocaleString() + (window.MARKET_LANG === "sq" ? " prona" : " listings") } } }, scales: { x: { grid: { display: false }, border: { display: false }, ticks: { color: muted } }, y: { grid: { color: grid }, border: { display: false }, ticks: { color: muted, callback: v => beds ? "€" + (v/1000) + "k" : v } } } } });
  }
  renderSignal("distribution");
  document.querySelectorAll("[data-chart]").forEach(button => button.addEventListener("click", () => { document.querySelectorAll("[data-chart]").forEach(b => b.classList.toggle("is-active", b === button)); renderSignal(button.dataset.chart); }));
  new Chart(document.getElementById("chartGrades"), { type: "doughnut", data: { labels: window.MARKET_LANG === "sq" ? ["Oferta të shkëlqyera", "Oferta të mira", "Çmim tregu"] : ["Great deals", "Good deals", "Market price"], datasets: [{ data: [S.by_grade.great, S.by_grade.good, S.by_grade.bad], backgroundColor: [colors.pink, colors.yellow, colors.cityBlue], borderColor: "#20201d", borderWidth: 3, spacing: 2, hoverOffset: 9 }] }, options: { responsive:true, maintainAspectRatio:false, cutout:"75%", rotation:-90, plugins:{ legend:{display:false}, tooltip:{backgroundColor:"#121b2e",padding:13} } } });
})();
