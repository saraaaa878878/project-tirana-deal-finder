(function () {
  const tray = document.getElementById("compareTray");
  const list = document.getElementById("compareItems");
  const count = document.getElementById("compareCount");
  const clear = document.getElementById("compareClear");
  const close = document.getElementById("compareClose");
  if (!tray || !list) return;

  const key = "tirana41_compare";
  let items = [];
  try { items = JSON.parse(localStorage.getItem(key)) || []; } catch (_) { items = []; }

  function euro(number) {
    return new Intl.NumberFormat("en", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(number);
  }

  function render(open) {
    count.textContent = `${items.length} / 3`;
    if (!items.length) {
      list.innerHTML = `<p>${list.dataset.empty || "Select up to 3 homes."}</p>`;
    } else {
      list.innerHTML = items.map(item => `
        <article>
          <button type="button" data-remove="${item.id}" aria-label="Remove">×</button>
          <a href="${item.url}">${item.address}</a>
          <b>${euro(item.price)}</b>
          <span>${item.sqm ? `${item.sqm} m²` : "—"} · ${item.grade}</span>
        </article>
      `).join("");
    }
    document.querySelectorAll("[data-compare]").forEach(button => {
      button.classList.toggle("is-selected", items.some(item => item.id === button.dataset.id));
    });
    localStorage.setItem(key, JSON.stringify(items));
    if (open) tray.classList.add("is-open");
  }

  document.addEventListener("click", event => {
    const button = event.target.closest("[data-compare]");
    if (button) {
      event.preventDefault();
      const existing = items.findIndex(item => item.id === button.dataset.id);
      if (existing >= 0) {
        items.splice(existing, 1);
      } else {
        if (items.length >= 3) items.shift();
        items.push({
          id: button.dataset.id,
          address: button.dataset.address,
          price: Number(button.dataset.price),
          sqm: Number(button.dataset.sqm),
          grade: button.dataset.grade,
          url: button.dataset.url
        });
      }
      render(true);
    }
    const remove = event.target.closest("[data-remove]");
    if (remove) {
      items = items.filter(item => item.id !== remove.dataset.remove);
      render(true);
    }
  });

  clear.addEventListener("click", () => { items = []; render(true); });
  close.addEventListener("click", () => tray.classList.remove("is-open"));
  render(false);
})();
