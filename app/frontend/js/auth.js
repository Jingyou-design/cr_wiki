import { apiRequest } from "./api.js";

export async function currentUser(options = {}) {
  return apiRequest("/api/auth/me", {
    method: "POST",
    ...options,
  });
}

export function routeForUser(user) {
  if (user.role === "admin") return "/admin";
  if (user.role === "manager") return "/manager";
  return "/chat";
}

export async function requirePageUser(roles) {
  let user;
  try {
    user = await currentUser();
  } catch {
    return null;
  }
  const allowedRoles = Array.isArray(roles) ? roles : [roles];
  if (!allowedRoles.includes(user.role)) {
    const target = routeForUser(user);
    if (window.location.pathname !== target) {
      window.location.replace(target);
    } else {
      console.error(
        `Role guard rejected ${user.role} on its own route ${target}.`,
      );
    }
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
      clearStoredChats();
      window.location.replace("/");
    }
  });
}

function clearStoredChats() {
  const prefix = "deepbook-chat:";
  try {
    for (let index = window.sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = window.sessionStorage.key(index);
      if (key?.startsWith(prefix)) {
        window.sessionStorage.removeItem(key);
      }
    }
  } catch {
    // Logout must still complete when browser storage is unavailable.
  }
}
