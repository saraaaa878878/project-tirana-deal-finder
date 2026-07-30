(function () {
  const points = window.MAP_POINTS || [];
  const mapNode = document.getElementById("map");
  if (typeof L === "undefined" || !mapNode) return;

  const lang = window.MARKET_LANG === "en" ? "en" : "sq";
  const frame = mapNode.closest(".map-frame");
  const explorer = mapNode.closest(".map-explorer");
  const toggleBtn = document.querySelector("[data-map-toggle]");

  const priceColors = {
    under_80k: "#f3a4bc",
    "80k_130k": "#ff4f87",
    "130k_200k": "#b72f5e",
    over_200k: "#531a30"
  };
  const gradeLabels = {
    great: { sq: "Ofertë e shkëlqyer", en: "Great deal" },
    good: { sq: "Ofertë e mirë", en: "Good deal" },
    bad: { sq: "Çmim tregu", en: "Market price" }
  };
  const tileUrls = {
    dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
  };

  const map = L.map(mapNode, { scrollWheelZoom: false, zoomControl: false, tap: true }).setView([41.3275, 19.8187], 12);
  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Klikimi mbi hartë "e zhbllokon" zoom-in me rrotë, që faqja të mos rrëshqasë pa dashje;
  // largimi i kursorit e rikyç sjelljen normale të scroll-it te faqja.
  mapNode.addEventListener("click", () => {
    map.scrollWheelZoom.enable();
    mapNode.classList.add("is-engaged");
  });
  mapNode.addEventListener("mouseleave", () => map.scrollWheelZoom.disable());

  let mode = "light";
  let activeBand = "all";
  let tileLayer = L.tileLayer(tileUrls[mode], {
    attribution: "© OpenStreetMap © CARTO",
    maxZoom: 19
  }).addTo(map);

  // sa me shume shtepi ne nje zone, aq me e erret behet ngjyra e saj
  const clusterShades = [
    { max: 4, fill: "#f3a4bc", text: "#11110f" },
    { max: 9, fill: "#ff4f87", text: "#11110f" },
    { max: 19, fill: "#b72f5e", text: "#fffaf5" },
    { max: Infinity, fill: "#531a30", text: "#fffaf5" }
  ];

  function shadeForCount(count) {
    return clusterShades.find(shade => count <= shade.max) || clusterShades[clusterShades.length - 1];
  }

  const cluster = L.markerClusterGroup({
    maxClusterRadius: 42,
    showCoverageOnHover: false,
    iconCreateFunction(group) {
      const count = group.getChildCount();
      const shade = shadeForCount(count);
      return L.divIcon({
        className: "price-cluster",
        html: `<i class="price-cluster__fill" style="background:${shade.fill}; box-shadow:0 0 0 7px ${shade.fill}33;"></i>` +
              `<span style="color:${shade.text};">${count}</span>`,
        iconSize: [42, 42]
      });
    }
  });
  map.addLayer(cluster);

  const popupLabel = mapNode.dataset.viewLabel || "View listing";
  const bedroomsWord = lang === "sq" ? "dhoma" : "bed";

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  function popupHtml(point) {
    const grade = gradeLabels[point.grade];
    const details = [];
    if (point.sqm) details.push(`${point.sqm} m²`);
    if (point.bedrooms) details.push(`${point.bedrooms} ${bedroomsWord}`);

    return `
      <div class="map-popup">
        ${point.image ? `<img class="map-popup__photo" src="${escapeHtml(point.image)}" alt="">` : ""}
        <div class="map-popup__body">
          <span>TIRANA/41</span>
          <b>€${point.price.toLocaleString()}</b>
          ${details.length ? `<small>${details.join(" · ")}</small>` : ""}
          ${point.address ? `<small class="map-popup__addr">${escapeHtml(point.address)}</small>` : ""}
          ${grade ? `<em class="map-popup__grade map-popup__grade--${point.grade}">${grade[lang]}</em>` : ""}
          <a href="/listing/${point.id}">${popupLabel} →</a>
        </div>
      </div>`;
  }

  function markerFor(point) {
    const fill = priceColors[point.band] || "#ff4f87";
    const marker = L.circleMarker([point.lat, point.lng], {
      radius: 4,
      weight: 1,
      color: mode === "light" ? "#fffaf5" : "#11110f",
      fillColor: fill,
      fillOpacity: 0.94
    });
    marker.bindPopup(popupHtml(point), { maxWidth: 220, className: "map-popup-wrap" });
    return marker;
  }

  function renderPoints() {
    cluster.clearLayers();
    points
      .filter(point => activeBand === "all" || point.band === activeBand)
      .forEach(point => cluster.addLayer(markerFor(point)));
  }

  function setMode(nextMode) {
    mode = nextMode;
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(tileUrls[mode], {
      attribution: "© OpenStreetMap © CARTO",
      maxZoom: 19
    }).addTo(map);
    tileLayer.bringToBack();
    explorer.dataset.mode = mode;
    renderPoints();
  }

  document.querySelectorAll("[data-map-band]").forEach(button => {
    button.addEventListener("click", () => {
      activeBand = button.dataset.mapBand;
      document.querySelectorAll("[data-map-band]").forEach(item => item.classList.toggle("is-active", item === button));
      renderPoints();
    });
  });

  document.querySelectorAll("[data-map-mode]").forEach(button => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-map-mode]").forEach(item => item.classList.toggle("is-active", item === button));
      setMode(button.dataset.mapMode);
    });
  });

  // Hap/mbyll hartën pa e hequr nga DOM-i, në mënyrë që Leaflet-i të mbetet gjallë
  // dhe harta të mos "prishet" kur rihapet.
  if (toggleBtn && frame) {
    const closeLabel = lang === "sq" ? "MBYLL HARTËN" : "CLOSE MAP";
    const openLabel = lang === "sq" ? "HAP HARTËN" : "OPEN MAP";
    toggleBtn.addEventListener("click", () => {
      const isOpen = toggleBtn.getAttribute("aria-expanded") === "true";
      toggleBtn.setAttribute("aria-expanded", String(!isOpen));
      toggleBtn.textContent = isOpen ? openLabel : closeLabel;
      frame.classList.toggle("is-collapsed", isOpen);
      if (isOpen) {
        map.scrollWheelZoom.disable();
      } else {
        setTimeout(() => map.invalidateSize(), 210);
      }
    });
  }

  renderPoints();
})();