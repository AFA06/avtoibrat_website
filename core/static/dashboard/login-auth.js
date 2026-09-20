(function () {
  "use strict";

  const ROLES = ["student", "staff"];
  const params = new URLSearchParams(window.location.search);

  const stepProfile = document.getElementById("step-profile");
  const stepCredentials = document.getElementById("step-credentials");
  const profileNext = document.getElementById("profile-next");
  const roleTitle = document.getElementById("role-title");
  const roleSubtitle = document.getElementById("role-subtitle");
  const roleInput = document.getElementById("role-input");
  const identifierFields = document.querySelectorAll("[data-role-field]");
  const forgotLink = document.getElementById("forgot-link");
  const cards = document.querySelectorAll(".login-profile");

  let selectedCard = null;

  function updateRoleInUrl(role) {
    const url = new URL(window.location.href);
    if (role) {
      url.searchParams.set("role", role);
    } else {
      url.searchParams.delete("role");
    }
    window.history.replaceState({}, "", url);
  }

  function selectCard(card) {
    selectedCard = card;
    cards.forEach((item) => {
      const active = item === card;
      item.classList.toggle("is-selected", active);
      item.setAttribute("aria-checked", String(active));
    });
    profileNext.disabled = false;
    roleTitle.textContent = card.dataset.title;
    roleSubtitle.textContent = card.dataset.description;
    roleInput.value = card.dataset.role;
    showIdentifierField(card.dataset.role);
  }

  function showIdentifierField(role) {
    identifierFields.forEach((field) => {
      const active = field.dataset.roleField === role;
      field.hidden = !active;
      field.querySelector("input").disabled = !active;
    });
  }

  function showCredentials() {
    if (!selectedCard) return;
    updateRoleInUrl(selectedCard.dataset.role);
    stepProfile.hidden = true;
    stepCredentials.hidden = false;
    forgotLink.href = `${forgotLink.dataset.baseUrl}?role=${encodeURIComponent(selectedCard.dataset.role)}`;
    document.querySelector("[data-role-field]:not([hidden]) input").focus();
  }

  function showProfile() {
    updateRoleInUrl(null);
    stepCredentials.hidden = true;
    stepProfile.hidden = false;
  }

  function cardForRole(role) {
    return Array.from(cards).find((card) => card.dataset.role === role);
  }

  cards.forEach((card) => card.addEventListener("click", () => selectCard(card)));
  profileNext.addEventListener("click", showCredentials);
  document.getElementById("go-back").addEventListener("click", showProfile);

  const requestedRole = params.get("role");
  const hasServerMessage = ["error", "expired", "device_limit"].some((key) => params.has(key));

  if (ROLES.includes(requestedRole)) {
    selectCard(cardForRole(requestedRole));
    showCredentials();
  } else if (hasServerMessage) {
    selectCard(cardForRole("student"));
    showCredentials();
  }
})();
