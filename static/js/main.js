(function () {
  "use strict";

  var header = document.querySelector("[data-nav]");
  if (!header) {
    return;
  }

  var toggle = header.querySelector(".nav-toggle");
  var nav = header.querySelector("#primary-nav");
  if (!toggle || !nav) {
    return;
  }

  function setOpen(isOpen) {
    header.classList.toggle("is-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.querySelector(".visually-hidden").textContent = isOpen ? "Закрыть меню" : "Открыть меню";
  }

  toggle.addEventListener("click", function () {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });

  nav.addEventListener("click", function (event) {
    if (event.target.closest("a")) {
      setOpen(false);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && header.classList.contains("is-open")) {
      setOpen(false);
      toggle.focus();
    }
  });

  var desktop = window.matchMedia("(min-width: 1024px)");
  desktop.addEventListener("change", function (event) {
    if (event.matches) {
      setOpen(false);
    }
  });
})();
