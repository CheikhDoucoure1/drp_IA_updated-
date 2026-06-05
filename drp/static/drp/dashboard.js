(function () {
  function navigateRow(row) {
    var href = row.getAttribute("data-href");
    if (href) {
      window.location.href = href;
    }
  }

  document.querySelectorAll(".drp-row-link[data-href]").forEach(function (row) {
    row.addEventListener("click", function (event) {
      if (event.target.closest("a, button")) {
        return;
      }
      navigateRow(row);
    });

    row.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        navigateRow(row);
      }
    });
  });
})();
