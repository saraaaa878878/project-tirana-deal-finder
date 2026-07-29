(function () {
  const points = window.MAP_POINTS || [];
  const mapNode = document.getElementById("map");
  if (typeof L === "undefined" || !mapNode) return;

  const priceColors = {
    under_80k: "#b8ff55",
    "80k_130k": "#8f7cff",
    "130k_200k": "#ffb84d",
    over_200k: "#ff647c"
  };
  const dealColors = {
    great: "#b8ff55",
    good: "#ffd166",
    bad: "#ff647c",
    unknown: "#b7b9c7"
  };
  const tileUrls = {
    midnight: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    paper: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    deal: "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
  };

  const map = L.map(mapNode, { scrollWheelZoom: false, zoomControl: false }).setView([41.3275, 19.8187], 12);
  L.control.zoom({ position: "bottomright" }).addTo(map);

  let mode = "midnight";
  let activeBand = "all";
  let tileLayer = L.tileLayer(tileUrls[mode], {
    attribution: "© OpenStreetMap © CARTO",
    maxZoom: 19
  }).addTo(map);
  const cluster = L.markerClusterGroup({
    maxClusterRadius: 42,
    showCoverageOnHover: false,
    iconCreateFunction(group) {
      return L.divIcon({
        className: "price-cluster",
        html: `<span>${group.getChildCount()}</span>`,
        iconSize: [42, 42]
      });
    }
  });
  map.addLayer(cluster);

  const popupLabel = mapNode.dataset.viewLabel || "View listing";

  function markerFor(point) {
    const fill = mode === "deal"
      ? (dealColors[point.grade] || dealColors.unknown)
      : (priceColors[point.band] || "#8f7cff");
    const marker = L.circleMarker([point.lat, point.lng], {
      radius: mode === "deal" ? 7 : 6,
      weight: 2,
      color: mode === "paper" ? "#171715" : "#0d0d0c",
      fillColor: fill,
      fillOpacity: 0.94
    });
    marker.bindPopup(
      `<div class="map-popup"><span>TIRANA/41</span><b>€${point.price.toLocaleString()}</b>` +
      `${point.sqm ? `<small>${point.sqm} m²</small>` : ""}` +
      `<a href="/listing/${point.id}">${popupLabel} →</a></div>`
    );
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
    mapNode.closest(".map-explorer").dataset.mode = mode;
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

  renderPoints();
})();
