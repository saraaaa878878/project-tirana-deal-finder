/* map.js — Leaflet cluster map of every listing, coloured by asking price */
(function () {
  const pts = window.MAP_POINTS || [];
  if (typeof L === "undefined" || !document.getElementById("map")) return;

  // Warm sequential ramp for PRICE (kept distinct from the green deal colours).
  const BAND_COLORS = {
    under_80k: "#E8C547",
    "80k_130k": "#E59B3B",
    "130k_200k": "#D9663B",
    over_200k: "#B23A48",
  };
  const BAND_LABELS = {
    under_80k: "Under \u20ac80k",
    "80k_130k": "\u20ac80k\u2013130k",
    "130k_200k": "\u20ac130k\u2013200k",
    over_200k: "Over \u20ac200k",
  };

  // Centre on Tirana; disable scroll-zoom so the page still scrolls over the map.
  const map = L.map("map", { scrollWheelZoom: false }).setView([41.3275, 19.8187], 12);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OpenStreetMap &copy; CARTO",
    maxZoom: 19,
  }).addTo(map);

  // Clustering keeps ~4,500 markers fast and readable.
  const cluster = L.markerClusterGroup({ maxClusterRadius: 50 });

  pts.forEach((p) => {
    const marker = L.circleMarker([p.lat, p.lng], {
      radius: 6,
      weight: 1,
      color: "#ffffff",
      fillColor: BAND_COLORS[p.band] || "#888888",
      fillOpacity: 0.9,
    });
    marker.bindPopup(
      "<b>\u20ac" + p.price.toLocaleString() + "</b><br>" +
      (p.sqm ? p.sqm + " m\u00b2<br>" : "") +
      '<a href="/listing/' + p.id + '">View listing &rarr;</a>'
    );
    cluster.addLayer(marker);
  });

  map.addLayer(cluster);

  // Legend
  const legend = L.control({ position: "bottomright" });
  legend.onAdd = function () {
    const div = L.DomUtil.create("div", "map-legend");
    div.innerHTML =
      '<div class="map-legend__title">Asking price</div>' +
      Object.keys(BAND_LABELS)
        .map(
          (b) =>
            '<div class="map-legend__row"><span class="map-legend__sw" style="background:' +
            BAND_COLORS[b] + '"></span>' + BAND_LABELS[b] + "</div>"
        )
        .join("");
    return div;
  };
  legend.addTo(map);
})();
