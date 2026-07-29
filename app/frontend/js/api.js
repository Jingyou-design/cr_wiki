export async function apiRequest(url, options = {}) {
  const { redirectUnauthorized = true, ...fetchOptions } = options;
  const response = await fetch(url, {
    credentials: "same-origin",
    ...fetchOptions,
  });
  const contentType = response.headers.get("content-type") || "";
  const responseText = await response.text();
  const data =
    contentType.includes("application/json") && responseText
      ? JSON.parse(responseText)
      : responseText
        ? { detail: responseText }
        : null;
  if (!response.ok) {
    if (response.status === 401 && redirectUnauthorized) {
      window.location.replace("/");
    }
    throw createApiError(response.status, data);
  }
  return data;
}

export async function streamChat(payload, onEvent) {
  const response = await fetch("/api/wiki/chat", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : { detail: await response.text() };
    if (response.status === 401) {
      window.location.replace("/");
    }
    throw createApiError(response.status, data);
  }
  if (!response.body) {
    throw new Error("浏览器没有收到流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    buffer = dispatchSseEvents(buffer, onEvent);
    if (done) break;
  }
  buffer += decoder.decode();
  if (buffer.trim()) dispatchSseEvent(buffer, onEvent);
}

function dispatchSseEvents(buffer, onEvent) {
  let boundary = buffer.match(/\r?\n\r?\n/);
  while (boundary && boundary.index !== undefined) {
    const rawEvent = buffer.slice(0, boundary.index);
    buffer = buffer.slice(boundary.index + boundary[0].length);
    dispatchSseEvent(rawEvent, onEvent);
    boundary = buffer.match(/\r?\n\r?\n/);
  }
  return buffer;
}

function dispatchSseEvent(rawEvent, onEvent) {
  let eventType = "message";
  const dataLines = [];
  for (const line of rawEvent.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") eventType = value;
    if (field === "data") dataLines.push(value);
  }
  if (dataLines.length === 0) return;
  const data = JSON.parse(dataLines.join("\n"));
  if (!data.type && eventType !== "message") data.type = eventType;
  onEvent(data);
}

function createApiError(status, data) {
  const detail =
    typeof data?.detail === "string"
      ? data.detail
      : data?.detail?.message || `请求失败（HTTP ${status}）`;
  const error = new Error(detail);
  error.status = status;
  error.data = data;
  return error;
}
