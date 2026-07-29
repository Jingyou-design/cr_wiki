import { apiRequest } from "./api.js";

export async function currentUser(options = {}) {
  return apiRequest("/api/auth/me", {
    method: "POST",
    ...options,
  });
}

export function routeForUser(user) {
  return user.role === "admin" ? "/admin" : "/chat";
}

export async function requirePageUser(role) {
  let user;
  try {
    user = await currentUser();
  } catch {
    return null;
  }
  if (user.role !== role) {
    window.location.replace(routeForUser(user));
    return null;
  }
  renderUser(user);
  bindLogout();
  return user;
}

function renderUser(user) {
  const chip = document.querySelector("#userChip");
  if (chip) {
    chip.textContent = `${user.username} · ${user.department_code}`;
  }
}

function bindLogout() {
  const button = document.querySelector("#logoutButton");
  if (!button) return;
  button.addEventListener("click", async () => {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } finally {
      window.location.replace("/");
    }
  });
}
