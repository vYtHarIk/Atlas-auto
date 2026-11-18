(function () {
  "use strict";

  var header = document.querySelector("[data-nav]");
  if (header) {
    var toggle = header.querySelector(".nav-toggle");
    var nav = header.querySelector("#primary-nav");

    if (toggle && nav) {
      var setOpen = function (isOpen) {
        header.classList.toggle("is-open", isOpen);
        toggle.setAttribute("aria-expanded", String(isOpen));
        var label = toggle.querySelector(".visually-hidden");
        if (label) {
          label.textContent = isOpen ? "Закрыть меню" : "Открыть меню";
        }
      };

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
    }
  }

  // Автоотправка сортировки каталога.
  document.querySelectorAll("[data-autosubmit]").forEach(function (control) {
    control.addEventListener("change", function () {
      var form = control.form || document.getElementById(control.getAttribute("form"));
      if (!form) {
        return;
      }
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    });
  });

  document.querySelectorAll("[data-filter-panel]").forEach(function (panel) {
    var toggle = panel.querySelector("[data-filter-toggle]");
    var label = panel.querySelector("[data-filter-toggle-label]");
    if (!toggle) {
      return;
    }

    var hasQuery = window.location.search.length > 1;
    panel.classList.add("is-collapsible");
    panel.classList.toggle("is-open", hasQuery);
    toggle.setAttribute("aria-expanded", String(hasQuery));

    var syncLabel = function (isOpen) {
      if (label) {
        label.textContent = isOpen ? "Скрыть" : "Показать";
      }
    };
    syncLabel(hasQuery);

    toggle.addEventListener("click", function () {
      var isOpen = !panel.classList.contains("is-open");
      panel.classList.toggle("is-open", isOpen);
      toggle.setAttribute("aria-expanded", String(isOpen));
      syncLabel(isOpen);
    });
  });

  document.querySelectorAll("[data-favorite]").forEach(function (button) {
    var form = button.form;
    if (!form) {
      return;
    }

    button.addEventListener("click", function (event) {
      event.preventDefault();
      var tokenField = form.querySelector("[name=csrfmiddlewaretoken]");
      var url = button.getAttribute("data-url");

      fetch(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": tokenField ? tokenField.value : "",
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json"
        },
        credentials: "same-origin"
      })
        .then(function (response) {
          if (response.redirected) {
            window.location.href = response.url;
            return null;
          }
          if (!response.ok) {
            throw new Error("request failed");
          }
          return response.json();
        })
        .then(function (data) {
          if (!data) {
            return;
          }
          var isFavorite = Boolean(data.is_favorite);
          button.classList.toggle("is-active", isFavorite);
          button.setAttribute("aria-pressed", String(isFavorite));
          button.setAttribute(
            "aria-label",
            isFavorite ? "Убрать из избранного" : "Добавить в избранное"
          );
          var label = button.querySelector("[data-favorite-label]");
          if (label) {
            label.textContent = isFavorite ? "В избранном" : "В избранное";
          }
        })
        .catch(function () {
          form.submit();
        });
    });
  });

  var PHONE = /^\+?[0-9\s\-()]{10,20}$/;

  function setError(field, message) {
    var wrapper =
      field.closest(".form-field") ||
      (field.closest(".form-check") && field.closest(".form-check").parentElement);
    if (!wrapper) {
      return;
    }
    wrapper.classList.add("has-error");
    field.setAttribute("aria-invalid", "true");
    var old = wrapper.querySelector("[data-client-error]");
    if (old) {
      old.remove();
    }
    var error = document.createElement("p");
    error.className = "form-error";
    error.setAttribute("data-client-error", "true");
    error.textContent = message;
    wrapper.appendChild(error);
  }

  function clearError(field) {
    var wrapper =
      field.closest(".form-field") ||
      (field.closest(".form-check") && field.closest(".form-check").parentElement);
    if (!wrapper) {
      return;
    }
    wrapper.classList.remove("has-error");
    field.removeAttribute("aria-invalid");
    var old = wrapper.querySelector("[data-client-error]");
    if (old) {
      old.remove();
    }
  }

  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    form.noValidate = true;

    form.addEventListener("input", function (event) {
      if (event.target.matches("input, select, textarea")) {
        clearError(event.target);
      }
    });

    form.addEventListener("change", function (event) {
      if (event.target.matches("input, select, textarea")) {
        clearError(event.target);
      }
    });

    form.addEventListener("submit", function (event) {
      var invalid = null;
      var controls = form.querySelectorAll("input, select, textarea");

      controls.forEach(function (field) {
        if (field.disabled || field.type === "hidden") {
          return;
        }
        var value = (field.value || "").trim();
        var message = "";

        if (field.type === "checkbox") {
          if (field.required && !field.checked) {
            message = "Отметьте этот пункт, чтобы продолжить.";
          }
        } else if (field.required && !value) {
          message = "Заполните это поле.";
        } else if (field.type === "file" && field.required && !field.files.length) {
          message = "Выберите файл.";
        } else if (field.hasAttribute("data-phone") && value && !PHONE.test(value)) {
          message = "Укажите телефон в формате +7 (900) 000-00-00.";
        } else if (field.type === "datetime-local" && value) {
          var moment = new Date(value).getTime();
          if (!Number.isNaN(moment) && moment < Date.now() + 60 * 60 * 1000) {
            message = "Выберите время не раньше чем через час.";
          }
        }

        if (message) {
          setError(field, message);
          if (!invalid) {
            invalid = field;
          }
        }
      });

      var passwords = form.querySelectorAll('input[autocomplete="new-password"]');
      if (passwords.length === 2) {
        var first = passwords[0].value;
        var second = passwords[1].value;
        if (first && second && first !== second) {
          setError(passwords[1], "Пароли не совпадают.");
          if (!invalid) {
            invalid = passwords[1];
          }
        }
      }

      if (invalid) {
        event.preventDefault();
        invalid.focus();
      }
    });
  });
})();
