(function () {
  const price = document.getElementById("propertyPrice");
  const down = document.getElementById("downPayment");
  const rate = document.getElementById("interestRate");
  const years = document.getElementById("loanYears");
  if (!price) return;
  const queryPrice = Number(new URLSearchParams(window.location.search).get("price"));
  if (queryPrice > 0) price.value = Math.round(queryPrice);
  const yearsWord = document.documentElement.lang === "sq" ? " vjet" : " years";
  const euro = n => new Intl.NumberFormat("en", {style: "currency", currency: "EUR", maximumFractionDigits: 0}).format(n);
  function calculate() {
    const p = Number(price.value) || 0;
    const downPct = Number(down.value);
    const principal = p * (1 - downPct / 100);
    const months = Number(years.value) * 12;
    const monthlyRate = Number(rate.value) / 1200;
    const payment = monthlyRate === 0 ? principal / months : principal * monthlyRate * Math.pow(1 + monthlyRate, months) / (Math.pow(1 + monthlyRate, months) - 1);
    const total = payment * months;
    const interest = total - principal;
    document.getElementById("downOutput").value = downPct + "%";
    document.getElementById("rateOutput").value = rate.value + "%";
    document.getElementById("yearsOutput").value = years.value + yearsWord;
    document.getElementById("monthlyPayment").textContent = euro(payment);
    document.getElementById("loanAmount").textContent = euro(principal);
    document.getElementById("totalInterest").textContent = euro(interest);
    document.getElementById("totalCost").textContent = euro(total + p * downPct / 100);
    const pct = total ? Math.round(principal / total * 100) : 0;
    document.getElementById("principalPercent").textContent = pct + "%";
    document.getElementById("loanRing").style.setProperty("--principal-angle", pct * 3.6 + "deg");
  }
  [price, down, rate, years].forEach(el => el.addEventListener("input", calculate));
  calculate();
})();
