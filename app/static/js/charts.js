(function () {
  const S = window.MARKET_STATS;
  if (!S || typeof Chart === "undefined") return;
  const muted = "#9b9b97", grid = "rgba(255,255,255,.12)";
  const colors = { violet: "#8f7cff", mint: "#b8ff55", yellow: "#ffd166", pink: "#ff647c" };
  Chart.defaults.font.family = "'Manrope', system-ui, sans-serif";
  Chart.defaults.color = muted;
  let signalChart;
  const gradient = (ctx, color) => { const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, ctx.chart.height); g.addColorStop(0, color); g.addColorStop(1, "rgba(8,14,29,0)"); return g; };
  function renderSignal(mode) {
    const beds = mode === "bedrooms", source = beds ? S.by_bedrooms : S.distribution;
    const labels = source.map(d => beds ? d.bedrooms + " bd" : d.label);
    const values = source.map(d => beds ? d.median_price : d.count);
    const peak = values.indexOf(Math.max(...values));
    document.getElementById("signalLabel").textContent = beds ? "HIGHEST MEDIAN" : "MOST ACTIVE RANGE";
    document.getElementById("signalValue").textContent = beds ? "€" + values[peak].toLocaleString() : labels[peak];
    if (signalChart) signalChart.destroy();
    signalChart = new Chart(document.getElementById("chartDistribution"), { type: "line", data: { labels, datasets: [{ data: values, borderColor: beds ? colors.mint : colors.violet, borderWidth: 3, tension: .42, fill: true, pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: "#171715", pointBorderColor: beds ? colors.mint : colors.violet, pointBorderWidth: 2, backgroundColor: ctx => gradient(ctx, beds ? "rgba(184,255,85,.28)" : "rgba(143,124,255,.32)") }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { displayColors: false, backgroundColor: "#f2efe8", titleColor: "#171715", bodyColor: "#55554f", padding: 14, callbacks: { label: c => beds ? "€" + c.parsed.y.toLocaleString() : c.parsed.y.toLocaleString() + " listings" } } }, scales: { x: { grid: { display: false }, border: { display: false }, ticks: { color: muted } }, y: { grid: { color: grid }, border: { display: false }, ticks: { color: muted, callback: v => beds ? "€" + (v/1000) + "k" : v } } } } });
  }
  renderSignal("distribution");
  document.querySelectorAll("[data-chart]").forEach(button => button.addEventListener("click", () => { document.querySelectorAll("[data-chart]").forEach(b => b.classList.toggle("is-active", b === button)); renderSignal(button.dataset.chart); }));
  new Chart(document.getElementById("chartGrades"), { type: "doughnut", data: { labels: ["Great deals", "Good deals", "Market price"], datasets: [{ data: [S.by_grade.great, S.by_grade.good, S.by_grade.bad], backgroundColor: [colors.mint, colors.yellow, colors.pink], hoverOffset: 9, borderWidth: 0 }] }, options: { responsive:true, maintainAspectRatio:false, cutout:"75%", rotation:-90, plugins:{ legend:{display:false}, tooltip:{backgroundColor:"#121b2e",padding:13} } } });
})();
