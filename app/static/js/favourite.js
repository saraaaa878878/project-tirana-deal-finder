(function () {
  document.querySelectorAll("[data-favourite]").forEach(button => {
    button.addEventListener("click", async function (event) {
      event.preventDefault();
      event.stopPropagation();
      button.disabled = true;
      try {
        const response = await fetch(button.dataset.url, { method: "POST" });
        if (response.redirected) {
          window.location = response.url;
          return;
        }
        const result = await response.json();
        button.classList.toggle("is-saved", result.saved);
        const label = button.querySelector("span");
        const icon = button.querySelector("b") || label;
        if (button.classList.contains("favourite-button")) {
          button.querySelector("span").textContent = result.saved ? button.dataset.saved : button.dataset.save;
          button.querySelector("b").textContent = result.saved ? "♥" : "♡";
        } else if (icon) {
          icon.textContent = result.saved ? "♥" : "♡";
        }
      } finally {
        button.disabled = false;
      }
    });
  });
})();
