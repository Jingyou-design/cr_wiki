import { apiRequest } from "./api.js";
import { currentUser, routeForUser } from "./auth.js";

const form = document.querySelector("#loginForm");
const username = document.querySelector("#loginUsername");
const password = document.querySelector("#loginPassword");
const errorMessage = document.querySelector("#loginError");
const button = document.querySelector("#loginButton");

try {
  const user = await currentUser({ redirectUnauthorized: false });
  window.location.replace(routeForUser(user));
} catch (error) {
  if (error.status !== 401) {
    errorMessage.textContent = error.message;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  errorMessage.textContent = "";
  button.disabled = true;
  button.querySelector("span").textContent = "正在核验";
  try {
    const user = await apiRequest("/api/auth/login", {
      method: "POST",
      redirectUnauthorized: false,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
      }),
    });
    password.value = "";
    window.location.replace(routeForUser(user));
  } catch (error) {
    password.value = "";
    errorMessage.textContent = error.message;
    username.focus();
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "登录";
  }
});
