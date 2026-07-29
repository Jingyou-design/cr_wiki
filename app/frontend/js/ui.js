export function showToast(message, kind = "success") {
  const region = document.querySelector("#toastRegion");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `toast${kind === "error" ? " is-error" : ""}`;
  toast.textContent = message;
  region.append(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

export function setBusy(button, busy, busyText, defaultText) {
  button.disabled = busy;
  button.classList.toggle("is-loading", busy);
  button.querySelector("span").textContent = busy ? busyText : defaultText;
  button.querySelector(".button-arrow").textContent = busy ? "↻" : "→";
}

export function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.min(
    Math.floor(Math.log(value) / Math.log(1024)),
    units.length - 1,
  );
  const amount = value / 1024 ** unitIndex;
  return `${amount.toFixed(amount >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}
