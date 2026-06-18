const MODULE_SWITCHES = [
  ["image", "IMAGE_MODULE_ENABLED"],
  ["localimage", "LOCAL_IMAGE_MODULE_ENABLED"],
  ["tts", "TTS_MODULE_ENABLED"],
  ["matrix", "MATRIX_MODULE_ENABLED"],
  ["printer", "PRINTER_MODULE_ENABLED"],
];

const STRINGS = {
  en: {
    eyebrow: "Local MCP Gateway",
    adminToken: ".env GATEWAY_TOKEN_HOST value",
    adminTokenPlaceholder: "Paste the value after GATEWAY_TOKEN_HOST=, without Bearer",
    connect: "Connect",
    runtime: "Runtime",
    server: "Server",
    address: "Address",
    container: "Container",
    docker: "Docker",
    ownership: "Config Ownership",
    snapshot: "Snapshot",
    ownedCount: "Owned fields",
    modules: "Modules",
    serverAndStorage: "Server & Storage",
    images: "Images",
    messaging: "Messaging",
    ttsPrinter: "TTS & Printer",
    save: "Save WebUI Config",
    reloadLocal: "Reload Local Values",
    saved: "Saved WebUI config. Restart the gateway to reload module registration when module switches change.",
    loaded: "Status loaded.",
    loadFailed: "Could not load status.",
    secretConfigured: "Configured; type a new value to replace",
  },
  "zh-CN": {
    eyebrow: "本地 MCP 网关",
    adminToken: ".env 中 GATEWAY_TOKEN_HOST 的值",
    adminTokenPlaceholder: "填写 GATEWAY_TOKEN_HOST= 后面的值，不要写 Bearer",
    connect: "连接",
    runtime: "运行状态",
    server: "服务",
    address: "地址",
    container: "容器",
    docker: "Docker",
    ownership: "配置归属",
    snapshot: "快照",
    ownedCount: "接管字段",
    modules: "模块",
    serverAndStorage: "服务与存储",
    images: "生图",
    messaging: "消息发送",
    ttsPrinter: "TTS 与打印",
    save: "保存 WebUI 配置",
    reloadLocal: "重新载入本地值",
    saved: "已保存 WebUI 配置。模块开关变化需要重启网关后重新注册工具。",
    loaded: "状态已载入。",
    loadFailed: "无法载入状态。",
    secretConfigured: "已配置；输入新值可替换",
  },
};

let lastStatus = null;

const $ = (selector) => document.querySelector(selector);

function language() {
  return localStorage.getItem("webui.language") || (navigator.language.startsWith("zh") ? "zh-CN" : "en");
}

function t(key) {
  return (STRINGS[language()] || STRINGS.en)[key] || STRINGS.en[key] || key;
}

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  $("#languageSelect").value = language();
}

function applyTheme() {
  const theme = localStorage.getItem("webui.theme") || "system";
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function authHeaders() {
  const token = $("#adminToken").value.trim() || localStorage.getItem("webui.adminToken") || "";
  if (token) {
    localStorage.setItem("webui.adminToken", token);
  }
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function loadStatus(showSuccess = true) {
  try {
    const response = await fetch("/admin/api/status", { headers: authHeaders() });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || response.statusText);
    lastStatus = payload;
    renderStatus(payload);
    renderForm(payload);
    if (showSuccess) showMessage(t("loaded"));
  } catch (error) {
    showMessage(`${t("loadFailed")} ${error.message}`);
  }
}

function renderStatus(payload) {
  $("#serverBadge").textContent = "online";
  $("#serverBadge").classList.remove("muted");
  $("#serverName").textContent = `${payload.server.name} ${payload.server.version}`;
  $("#serverAddress").textContent = `${payload.server.host}:${payload.server.port}`;
  $("#containerStatus").textContent = payload.environment.inside_container ? "yes" : "no";
  $("#dockerStatus").textContent = payload.environment.docker_cli?.available ? "available" : "not available";
  $("#webuiBadge").textContent = payload.webui.enabled ? "webui" : "local";
  $("#webuiBadge").classList.toggle("muted", !payload.webui.enabled);
  $("#snapshotPath").textContent = payload.webui.active_snapshot || "-";
  $("#ownedCount").textContent = Object.keys(payload.webui.owned_fields || {}).length;
}

function renderForm(payload) {
  const owned = payload.webui.owned_fields || {};
  const local = payload.local_env || {};
  const values = { ...local, ...owned };
  for (const [moduleName, envName] of MODULE_SWITCHES) {
    const input = document.querySelector(`[name="${envName}"]`);
    if (input) input.checked = normalizeBool(values[envName]);
  }
  document.querySelectorAll("#configForm input:not([type='checkbox'])").forEach((input) => {
    const value = values[input.name] || "";
    if (input.type === "password" && value) {
      input.value = "";
      input.placeholder = t("secretConfigured");
      return;
    }
    input.value = value;
  });
}

function renderModules() {
  const grid = $("#moduleGrid");
  grid.innerHTML = "";
  for (const [moduleName, envName] of MODULE_SWITCHES) {
    const tile = document.createElement("div");
    tile.className = "module-tile";
    tile.innerHTML = `
      <strong>${moduleName}</strong>
      <label>
        <input type="checkbox" name="${envName}" />
        <span>${envName}</span>
      </label>
    `;
    grid.append(tile);
  }
}

async function saveConfig(event) {
  event.preventDefault();
  const owned = {};
  for (const [, envName] of MODULE_SWITCHES) {
    owned[envName] = document.querySelector(`[name="${envName}"]`).checked ? "true" : "false";
  }
  document.querySelectorAll("#configForm input:not([type='checkbox'])").forEach((input) => {
    if (input.value.trim()) owned[input.name] = input.value.trim();
  });
  const response = await fetch("/admin/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ owned_fields: owned }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    showMessage(payload.error || response.statusText);
    return;
  }
  showMessage(t("saved"));
  await loadStatus(false);
}

function showMessage(text) {
  const node = $("#message");
  node.textContent = text;
  node.hidden = false;
}

function normalizeBool(value) {
  return ["1", "true", "yes", "on"].includes(String(value || "").toLowerCase());
}

function init() {
  $("#adminToken").value = localStorage.getItem("webui.adminToken") || "";
  $("#loadStatus").addEventListener("click", () => loadStatus());
  $("#configForm").addEventListener("submit", saveConfig);
  $("#resetDraft").addEventListener("click", () => lastStatus && renderForm(lastStatus));
  $("#languageSelect").addEventListener("change", (event) => {
    localStorage.setItem("webui.language", event.target.value);
    applyI18n();
  });
  $("#themeToggle").addEventListener("click", () => {
    const current = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("webui.theme", current);
    applyTheme();
  });
  applyTheme();
  applyI18n();
  renderModules();
  if ($("#adminToken").value) loadStatus(false);
}

init();
