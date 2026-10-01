// Whole table rows are clickable (the name link stays the keyboard-accessible target).
document.querySelectorAll("tr[data-href]").forEach((row) => {
  row.addEventListener("click", (event) => {
    if (!event.target.closest("a, button")) window.location.href = row.dataset.href;
  });
});
