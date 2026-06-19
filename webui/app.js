const MODULE_IDS = ["dashboard", "image", "localimage", "tts", "matrix", "printer"];

const MODULE_SWITCHES = {
  image: "IMAGE_MODULE_ENABLED",
  localimage: "LOCAL_IMAGE_MODULE_ENABLED",
  tts: "TTS_MODULE_ENABLED",
  matrix: "MATRIX_MODULE_ENABLED",
  printer: "PRINTER_MODULE_ENABLED",
};

const WORKFLOWS = {
  sdxl: {
    label: "SDXL",
    path: "./config/comfyui/sdxl_text_to_image.example.json",
    defaults: {
      LOCAL_IMAGE_COMFYUI_CHECKPOINT: "your-checkpoint.safetensors",
      LOCAL_IMAGE_COMFYUI_UNET_NAME: "",
      LOCAL_IMAGE_COMFYUI_CLIP_NAME: "",
      LOCAL_IMAGE_COMFYUI_VAE_NAME: "",
    },
    fields: ["LOCAL_IMAGE_COMFYUI_CHECKPOINT"],
  },
  anima: {
    label: "Anima",
    path: "./config/comfyui/anima_text_to_image.example.json",
    defaults: {
      LOCAL_IMAGE_COMFYUI_CHECKPOINT: "",
      LOCAL_IMAGE_COMFYUI_UNET_NAME: "miaomiaoRealskin_anima10.safetensors",
      LOCAL_IMAGE_COMFYUI_CLIP_NAME: "miaomiaoRealskin_anima10_txt.safetensors",
      LOCAL_IMAGE_COMFYUI_VAE_NAME: "qwen_image_vae.safetensors",
    },
    fields: ["LOCAL_IMAGE_COMFYUI_UNET_NAME", "LOCAL_IMAGE_COMFYUI_CLIP_NAME", "LOCAL_IMAGE_COMFYUI_VAE_NAME"],
  },
  custom: {
    label: "Custom",
    path: "",
    defaults: {},
    fields: [
      "LOCAL_IMAGE_COMFYUI_CHECKPOINT",
      "LOCAL_IMAGE_COMFYUI_UNET_NAME",
      "LOCAL_IMAGE_COMFYUI_CLIP_NAME",
      "LOCAL_IMAGE_COMFYUI_VAE_NAME",
    ],
  },
};

const FIELD_META = {
  IMAGE_API_BASE_URL: { label: "field.apiBaseUrl", requiredWhen: "image", placeholder: "https://api.example.com" },
  IMAGE_API_MODEL: { label: "field.model", requiredWhen: "image" },
  IMAGE_API_KEY: { label: "field.apiKey", requiredWhen: "image", secret: true },
  IMAGE_TOTAL_TIMEOUT_SECONDS: { label: "field.totalTimeout", type: "number" },
  IMAGE_PROVIDER_TIMEOUT_SECONDS: { label: "field.providerTimeout", type: "number" },
  IMAGE_MAX_DOWNLOAD_BYTES: { label: "field.maxDownloadBytes", type: "number" },

  LOCAL_IMAGE_COMFYUI_BASE_URL: { label: "field.comfyBaseUrl", requiredWhen: "localimage", placeholder: "http://127.0.0.1:8188" },
  LOCAL_IMAGE_COMFYUI_ALLOWED_HOST: { label: "field.allowedHost", requiredWhen: "localimage" },
  LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH: { label: "field.workflowPath", requiredWhen: "localimage" },
  LOCAL_IMAGE_DEFAULT_SIZE: { label: "field.defaultSize" },
  LOCAL_IMAGE_DEFAULT_QUALITY: { label: "field.defaultQuality" },
  LOCAL_IMAGE_DEFAULT_STYLE: { label: "field.defaultStyle" },
  LOCAL_IMAGE_DEFAULT_OUTPUT_FORMAT: { label: "field.defaultFormat" },
  LOCAL_IMAGE_COMFYUI_CHECKPOINT: { label: "Checkpoint" },
  LOCAL_IMAGE_COMFYUI_UNET_NAME: { label: "UNet Name" },
  LOCAL_IMAGE_COMFYUI_CLIP_NAME: { label: "CLIP Name" },
  LOCAL_IMAGE_COMFYUI_VAE_NAME: { label: "VAE Name" },
  LOCAL_IMAGE_COMFYUI_TIMEOUT_SECONDS: { label: "field.requestTimeout", type: "number" },
  LOCAL_IMAGE_COMFYUI_POLL_INTERVAL_SECONDS: { label: "field.pollInterval", type: "number" },
  LOCAL_IMAGE_COMFYUI_MAX_WAIT_SECONDS: { label: "field.maxWait", type: "number" },

  TTS_LOCAL_HTTP_URL: { label: "field.localHttpUrl", requiredWhen: "tts" },
  TTS_API_KEY: { label: "field.apiKey", secret: true },
  TTS_TOTAL_TIMEOUT_SECONDS: { label: "field.totalTimeout", type: "number" },
  TTS_PROVIDER_TIMEOUT_SECONDS: { label: "field.providerTimeout", type: "number" },

  MATRIX_HOMESERVER: { label: "Homeserver", requiredWhen: "matrix", placeholder: "http://127.0.0.1:8008" },
  MATRIX_TIMEOUT_SECONDS: { label: "field.timeout", type: "number" },
  MATRIX_MAX_TEXT_CHARS: { label: "field.maxTextChars", type: "number" },

  PRINTER_BRIDGE_URL: { label: "field.bridgeUrl", requiredWhen: "printer" },
  PRINTER_BRIDGE_API_KEY: { label: "field.apiKey", secret: true },
  PRINTER_MAX_COPIES: { label: "field.maxCopies", type: "number" },
  PRINTER_MAX_FILE_BYTES: { label: "field.maxFileBytes", type: "number" },
  PRINTER_BRIDGE_TIMEOUT_SECONDS: { label: "field.bridgeTimeout", type: "number" },
};

const STRINGS = {
  "zh-CN": {
    brandSubtitle: "gateway console",
    connected: "已连接",
    disconnected: "未连接",
    connect: "连接",
    adminToken: "Admin Token",
    adminTokenPlaceholder: "config/config.yaml 中 host_assistant.token 的值",
    footerHint: "保存后如模块开关变化，需要重启服务重新注册工具。",
    themeSystem: "跟随系统",
    themeLight: "日间",
    themeDark: "夜间",
    reload: "重新载入",
    configuredReplace: "已配置，输入新值可覆盖",
    required: "必填",
    configured: "已配置",
    notConfigured: "未配置",
    statusLoaded: "状态已载入。",
    loadFailed: "无法载入状态：{message}",
    fillRequired: "请先补齐带 * 的必填项。",
    saved: "已保存 WebUI 配置。模块注册和 agent 变更需要重启服务后完全生效。",
    agentNamePrompt: "请输入 agent 名称，只能包含字母、数字、下划线和连字符。",
    agentNameInvalid: "agent 名称只能包含字母、数字、下划线和连字符。",
    sharedArtifactRead: "共享 artifact 读取",
    highRiskTools: "High-risk tools",
    remove: "删除",
    addAgentTitle: "添加 agent",
    existingConfig: "已有配置片段",
    newConfig: "新建配置",
    existingTokenFile: "已有 token 文件",
    newTokenFile: "新建 token 文件",
    noAgentTitle: "还没有 agent",
    noAgentBody: "点击上方 + 输入名称后创建 Matrix agent 配置。",
    modules: {
      dashboard: { label: "Dashboard", title: "控制台", kicker: "Overview" },
      image: { label: "远程生图", title: "远程生图配置", kicker: "OpenAI-compatible" },
      localimage: { label: "本地生图", title: "本地生图配置", kicker: "ComfyUI" },
      tts: { label: "TTS", title: "TTS 配置", kicker: "Audio" },
      matrix: { label: "Matrix", title: "Matrix Agent 配置", kicker: "Messaging" },
      printer: { label: "打印机", title: "打印机配置", kicker: "Bridge" },
    },
    dashboard: {
      identityTitle: "身份与运行状态",
      identityDesc: "Dashboard 用来确认 WebUI 权限、服务状态和模块总开关。",
      service: "服务",
      address: "地址",
      webui: "WebUI",
      webuiOwned: "已接管部分字段",
      localConfig: "本地配置",
      agent: "Agent",
      agentCount: "{count} 个",
      moduleSwitches: "模块开关",
      moduleSwitchesDesc: "这里控制模块是否在重启后注册为 MCP 工具。",
      envTitle: "环境检测",
      envDesc: "已移除 Docker 检测，只保留本项目运行所需项目。",
      save: "保存 Dashboard 配置",
    },
    module: {
      enabledDesc: "模块已开启，必填项会参与配置完整度检查。",
      disabledDesc: "模块关闭时会保留配置，但不会注册对应工具。",
      enabledReady: "配置可用",
      disabled: "未启用",
      missing: "{count} 项必填缺失",
      save: "保存此模块",
    },
    localimage: {
      desc: "先选工作流，下面需要填写的模型字段会随选择变化。",
      modelFields: "{workflow} 模型字段",
      advanced: "高级超时设置",
      save: "保存本地生图",
    },
    matrix: {
      desc: "点击加号创建 agent。创建后再填写该 agent 的 Gateway Token 和 Matrix Token。",
      save: "保存 Matrix 配置",
    },
    field: {
      apiBaseUrl: "API Base URL",
      model: "模型",
      apiKey: "API Key",
      totalTimeout: "总超时秒数",
      providerTimeout: "Provider 超时秒数",
      maxDownloadBytes: "最大下载字节",
      comfyBaseUrl: "ComfyUI Base URL",
      allowedHost: "允许 Host",
      workflowPath: "Workflow Path",
      defaultSize: "默认尺寸",
      defaultQuality: "默认质量",
      defaultStyle: "默认风格",
      defaultFormat: "默认格式",
      requestTimeout: "请求超时秒数",
      pollInterval: "轮询间隔秒数",
      maxWait: "最大等待秒数",
      localHttpUrl: "Local HTTP URL",
      timeout: "超时秒数",
      maxTextChars: "最大文本字符数",
      bridgeUrl: "Bridge URL",
      maxCopies: "最大份数",
      maxFileBytes: "最大文件字节",
      bridgeTimeout: "Bridge 超时秒数",
    },
    empty: {
      title: "连接后显示配置",
      body: "输入 Admin Token 后载入当前运行状态和本地配置。",
    },
  },
  en: {
    brandSubtitle: "gateway console",
    connected: "Connected",
    disconnected: "Disconnected",
    connect: "Connect",
    adminToken: "Admin Token",
    adminTokenPlaceholder: "Value of callers.host_assistant.token in config/config.yaml",
    footerHint: "Restart the service after module switch changes so tools can be registered again.",
    themeSystem: "System",
    themeLight: "Light",
    themeDark: "Dark",
    reload: "Reload",
    configuredReplace: "Configured; type a new value to replace",
    required: "Required",
    configured: "Configured",
    notConfigured: "Not configured",
    statusLoaded: "Status loaded.",
    loadFailed: "Could not load status: {message}",
    fillRequired: "Please fill the required fields marked with *.",
    saved: "Saved WebUI config. Restart the service for module registration and agent changes to fully apply.",
    agentNamePrompt: "Enter an agent name. Use only letters, numbers, underscores, and hyphens.",
    agentNameInvalid: "Agent names may contain only letters, numbers, underscores, and hyphens.",
    sharedArtifactRead: "Shared artifact read",
    highRiskTools: "High-risk tools",
    remove: "Remove",
    addAgentTitle: "Add agent",
    existingConfig: "Existing config fragment",
    newConfig: "New config",
    existingTokenFile: "Token in YAML",
    newTokenFile: "New token in YAML",
    noAgentTitle: "No agents yet",
    noAgentBody: "Click + above, enter a name, then create a Matrix agent config.",
    modules: {
      dashboard: { label: "Dashboard", title: "Dashboard", kicker: "Overview" },
      image: { label: "Remote Image", title: "Remote Image Config", kicker: "OpenAI-compatible" },
      localimage: { label: "Local Image", title: "Local Image Config", kicker: "ComfyUI" },
      tts: { label: "TTS", title: "TTS Config", kicker: "Audio" },
      matrix: { label: "Matrix", title: "Matrix Agent Config", kicker: "Messaging" },
      printer: { label: "Printer", title: "Printer Config", kicker: "Bridge" },
    },
    dashboard: {
      identityTitle: "Identity And Runtime",
      identityDesc: "Dashboard verifies WebUI access, service status, and module switches.",
      service: "Service",
      address: "Address",
      webui: "WebUI",
      webuiOwned: "Owns some fields",
      localConfig: "Local config",
      agent: "Agent",
      agentCount: "{count}",
      moduleSwitches: "Module Switches",
      moduleSwitchesDesc: "Controls whether modules register MCP tools after restart.",
      envTitle: "Environment Checks",
      envDesc: "Docker checks were removed; only project runtime checks remain.",
      save: "Save Dashboard Config",
    },
    module: {
      enabledDesc: "The module is enabled; required fields count toward config completeness.",
      disabledDesc: "The module is disabled; config is kept but tools are not registered.",
      enabledReady: "Configured",
      disabled: "Disabled",
      missing: "{count} required missing",
      save: "Save Module",
    },
    localimage: {
      desc: "Choose a workflow first; model fields below change with the selection.",
      modelFields: "{workflow} model fields",
      advanced: "Advanced timeout settings",
      save: "Save Local Image",
    },
    matrix: {
      desc: "Click plus to create an agent. Fill Gateway Token and Matrix Token after creation.",
      save: "Save Matrix Config",
    },
    field: {
      apiBaseUrl: "API Base URL",
      model: "Model",
      apiKey: "API Key",
      totalTimeout: "Total timeout seconds",
      providerTimeout: "Provider timeout seconds",
      maxDownloadBytes: "Max download bytes",
      comfyBaseUrl: "ComfyUI Base URL",
      allowedHost: "Allowed Host",
      workflowPath: "Workflow Path",
      defaultSize: "Default size",
      defaultQuality: "Default quality",
      defaultStyle: "Default style",
      defaultFormat: "Default format",
      requestTimeout: "Request timeout seconds",
      pollInterval: "Poll interval seconds",
      maxWait: "Max wait seconds",
      localHttpUrl: "Local HTTP URL",
      timeout: "Timeout seconds",
      maxTextChars: "Max text chars",
      bridgeUrl: "Bridge URL",
      maxCopies: "Max copies",
      maxFileBytes: "Max file bytes",
      bridgeTimeout: "Bridge timeout seconds",
    },
    empty: {
      title: "Connect To Show Config",
      body: "Enter the Admin Token to load runtime status and local config.",
    },
  },
};

let lastStatus = null;
let currentPage = "dashboard";
let draftAgents = [];
let activeAgent = null;

const $ = (selector) => document.querySelector(selector);

function language() {
  const saved = localStorage.getItem("webui.language");
  if (saved && STRINGS[saved]) return saved;
  return navigator.language.toLowerCase().startsWith("zh") ? "zh-CN" : "en";
}

function t(key, vars = {}) {
  const parts = key.split(".");
  let value = STRINGS[language()];
  for (const part of parts) value = value?.[part];
  if (value == null) {
    value = STRINGS.en;
    for (const part of parts) value = value?.[part];
  }
  const text = String(value ?? key);
  return Object.entries(vars).reduce((result, [name, item]) => result.replaceAll(`{${name}}`, String(item)), text);
}

function moduleText(moduleId) {
  return t(`modules.${moduleId}`);
}

function getValues() {
  const owned = lastStatus?.webui?.owned_fields || {};
  const local = lastStatus?.local_env || {};
  return { ...local, ...owned };
}

function getValue(name) {
  return getValues()[name] || "";
}

function moduleEnabled(moduleId) {
  const envName = MODULE_SWITCHES[moduleId];
  return normalizeBool(getValue(envName));
}

function init() {
  $("#adminToken").value = localStorage.getItem("webui.adminToken") || "";
  $("#loadStatus").addEventListener("click", () => loadStatus());
  $("#configForm").addEventListener("submit", saveConfig);
  $("#themeSelect").addEventListener("change", (event) => {
    localStorage.setItem("webui.theme", event.target.value);
    applyTheme();
    applyStaticI18n();
  });
  $("#languageSelect").addEventListener("change", (event) => {
    localStorage.setItem("webui.language", event.target.value);
    applyStaticI18n();
    renderAll();
  });
  applyTheme();
  applyStaticI18n();
  renderNav();
  routeTo(location.hash.replace("#", "") || "dashboard");
  window.addEventListener("hashchange", () => routeTo(location.hash.replace("#", "") || "dashboard"));
  if ($("#adminToken").value) loadStatus(false);
}

function applyStaticI18n() {
  document.documentElement.lang = language();
  $("#brandSubtitle").textContent = t("brandSubtitle");
  $("#adminTokenLabel").innerHTML = `${t("adminToken")} <b>*</b>`;
  $("#adminToken").placeholder = t("adminTokenPlaceholder");
  $("#loadStatus").textContent = t("connect");
  $("#dirtyInfo").textContent = t("footerHint");
  $("#languageSelect").value = language();
  $("#themeSelect").value = localStorage.getItem("webui.theme") || "system";
  $("#themeSelect").options[0].textContent = t("themeSystem");
  $("#themeSelect").options[1].textContent = t("themeLight");
  $("#themeSelect").options[2].textContent = t("themeDark");
  updateHeader();
}

async function loadStatus(showSuccess = true) {
  try {
    const response = await fetch("/admin/api/status", { headers: authHeaders() });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || response.statusText);
    lastStatus = payload;
    draftAgents = normalizeAgents(payload.agents || []);
    activeAgent = draftAgents[0]?.name || null;
    renderAll();
    if (showSuccess) showMessage(t("statusLoaded"), "success");
  } catch (error) {
    showMessage(t("loadFailed", { message: error.message }), "danger");
  }
}

function authHeaders() {
  const token = $("#adminToken").value.trim() || localStorage.getItem("webui.adminToken") || "";
  if (token) localStorage.setItem("webui.adminToken", token);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function renderAll() {
  renderNav();
  updateHeader();
  renderPage();
  updateFooter();
}

function renderNav() {
  const nav = $("#sidebarNav");
  nav.innerHTML = MODULE_IDS.map((id) => {
    const active = id === currentPage ? " active" : "";
    const badge = id !== "dashboard" && moduleEnabled(id) ? '<span class="mini-dot on"></span>' : '<span class="mini-dot"></span>';
    return `<a class="nav-item${active}" href="#${id}">${badge}<span>${t(`modules.${id}.label`)}</span></a>`;
  }).join("");
}

function routeTo(page) {
  currentPage = MODULE_IDS.includes(page) ? page : "dashboard";
  updateHeader();
  renderNav();
  renderPage();
}

function updateHeader() {
  $("#pageTitle").textContent = t(`modules.${currentPage}.title`);
  $("#pageKicker").textContent = t(`modules.${currentPage}.kicker`);
  const badge = $("#runtimeBadge");
  badge.textContent = lastStatus ? t("connected") : t("disconnected");
  badge.className = `status-pill ${lastStatus ? "success" : "muted"}`;
}

function updateFooter() {
  $("#snapshotInfo").textContent = `Config: ${lastStatus?.webui?.active_snapshot || "-"}`;
}

function renderPage() {
  const mount = $("#pageMount");
  if (!lastStatus) {
    mount.innerHTML = emptyState(t("empty.title"), t("empty.body"));
    return;
  }
  if (currentPage === "dashboard") renderDashboard(mount);
  if (currentPage === "image") renderModulePage(mount, "image", [
    "IMAGE_API_BASE_URL",
    "IMAGE_API_MODEL",
    "IMAGE_API_KEY",
    "IMAGE_TOTAL_TIMEOUT_SECONDS",
    "IMAGE_PROVIDER_TIMEOUT_SECONDS",
    "IMAGE_MAX_DOWNLOAD_BYTES",
  ]);
  if (currentPage === "localimage") renderLocalImagePage(mount);
  if (currentPage === "tts") renderModulePage(mount, "tts", [
    "TTS_LOCAL_HTTP_URL",
    "TTS_API_KEY",
    "TTS_TOTAL_TIMEOUT_SECONDS",
    "TTS_PROVIDER_TIMEOUT_SECONDS",
  ]);
  if (currentPage === "matrix") renderMatrixPage(mount);
  if (currentPage === "printer") renderModulePage(mount, "printer", [
    "PRINTER_BRIDGE_URL",
    "PRINTER_BRIDGE_API_KEY",
    "PRINTER_MAX_COPIES",
    "PRINTER_MAX_FILE_BYTES",
    "PRINTER_BRIDGE_TIMEOUT_SECONDS",
  ]);
  attachDynamicHandlers();
}

function renderDashboard(mount) {
  const modules = Object.keys(MODULE_SWITCHES);
  mount.innerHTML = `
    <section class="dashboard-grid">
      <article class="panel span-2">
        <div class="panel-heading">
          <div>
            <h2>${t("dashboard.identityTitle")}</h2>
            <p>${t("dashboard.identityDesc")}</p>
          </div>
          <span class="status-pill success">admin</span>
        </div>
        <div class="status-grid">
          ${statusFact(t("dashboard.service"), `${lastStatus.server.name} ${lastStatus.server.version}`, "success")}
          ${statusFact(t("dashboard.address"), `${lastStatus.server.host}:${lastStatus.server.port}`, "neutral")}
          ${statusFact(t("dashboard.webui"), lastStatus.webui.enabled ? t("dashboard.webuiOwned") : t("dashboard.localConfig"), lastStatus.webui.enabled ? "warning" : "neutral")}
          ${statusFact(t("dashboard.agent"), t("dashboard.agentCount", { count: draftAgents.length }), draftAgents.length ? "success" : "neutral")}
        </div>
      </article>

      <article class="panel span-2">
        <div class="panel-heading">
          <div>
            <h2>${t("dashboard.moduleSwitches")}</h2>
            <p>${t("dashboard.moduleSwitchesDesc")}</p>
          </div>
        </div>
        <div class="module-switch-grid">
          ${modules.map((id) => moduleSwitchCard(id)).join("")}
        </div>
      </article>

      <article class="panel span-2">
        <div class="panel-heading">
          <div>
            <h2>${t("dashboard.envTitle")}</h2>
            <p>${t("dashboard.envDesc")}</p>
          </div>
        </div>
        <div class="check-list">
          ${environmentRows()}
        </div>
      </article>
    </section>
    ${actionBar(t("dashboard.save"))}
  `;
}

function renderModulePage(mount, moduleId, fields) {
  mount.innerHTML = `
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>${t(`modules.${moduleId}.label`)}</h2>
          <p>${moduleEnabled(moduleId) ? t("module.enabledDesc") : t("module.disabledDesc")}</p>
        </div>
        ${moduleToggle(moduleId)}
      </div>
      <div class="form-grid">
        ${fields.map((name) => field(name)).join("")}
      </div>
    </section>
    ${actionBar(t("module.save"))}
  `;
}

function renderLocalImagePage(mount) {
  const selected = inferWorkflow();
  const workflow = WORKFLOWS[selected];
  const baseFields = [
    "LOCAL_IMAGE_COMFYUI_BASE_URL",
    "LOCAL_IMAGE_COMFYUI_ALLOWED_HOST",
    "LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH",
    "LOCAL_IMAGE_DEFAULT_SIZE",
    "LOCAL_IMAGE_DEFAULT_QUALITY",
    "LOCAL_IMAGE_DEFAULT_STYLE",
    "LOCAL_IMAGE_DEFAULT_OUTPUT_FORMAT",
  ];
  const advancedFields = [
    "LOCAL_IMAGE_COMFYUI_TIMEOUT_SECONDS",
    "LOCAL_IMAGE_COMFYUI_POLL_INTERVAL_SECONDS",
    "LOCAL_IMAGE_COMFYUI_MAX_WAIT_SECONDS",
  ];
  mount.innerHTML = `
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>ComfyUI</h2>
          <p>${t("localimage.desc")}</p>
        </div>
        ${moduleToggle("localimage")}
      </div>
      <div class="segmented" id="workflowSelect">
        ${Object.entries(WORKFLOWS).map(([id, item]) => `<button type="button" data-workflow="${id}" class="${id === selected ? "selected" : ""}">${workflowLabel(id, item)}</button>`).join("")}
      </div>
      <div class="form-grid">
        ${baseFields.map((name) => field(name)).join("")}
      </div>
      <div class="subsection">
        <h3>${t("localimage.modelFields", { workflow: workflowLabel(selected, workflow) })}</h3>
        <div class="form-grid">
          ${workflow.fields.map((name) => field(name, { required: moduleEnabled("localimage") && selected !== "custom" })).join("")}
        </div>
      </div>
      <details class="advanced">
        <summary>${t("localimage.advanced")}</summary>
        <div class="form-grid">
          ${advancedFields.map((name) => field(name)).join("")}
        </div>
      </details>
    </section>
    ${actionBar(t("localimage.save"))}
  `;
}

function renderMatrixPage(mount) {
  const active = draftAgents.find((agent) => agent.name === activeAgent) || draftAgents[0] || null;
  if (active && active.name !== activeAgent) activeAgent = active.name;
  mount.innerHTML = `
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>Matrix</h2>
          <p>${t("matrix.desc")}</p>
        </div>
        ${moduleToggle("matrix")}
      </div>
      <div class="form-grid compact">
        ${field("MATRIX_HOMESERVER")}
        ${field("MATRIX_TIMEOUT_SECONDS")}
        ${field("MATRIX_MAX_TEXT_CHARS")}
      </div>
      <div class="agent-bar">
        ${draftAgents.map((agent) => `<button type="button" class="agent-tab ${agent.name === activeAgent ? "active" : ""}" data-agent="${escapeHtml(agent.name)}">${escapeHtml(agent.name)}</button>`).join("")}
        <button type="button" id="addAgent" class="agent-add" title="${t("addAgentTitle")}">+</button>
      </div>
      <div id="agentPanel">
        ${active ? agentPanel(active) : emptyState(t("noAgentTitle"), t("noAgentBody"))}
      </div>
    </section>
    ${actionBar(t("matrix.save"))}
  `;
}

function moduleSwitchCard(moduleId) {
  const enabled = moduleEnabled(moduleId);
  const missing = requiredMissing(moduleId);
  return `
    <div class="module-card ${enabled ? "enabled" : ""}">
      <div>
        <strong>${t(`modules.${moduleId}.label`)}</strong>
        <span>${enabled ? (missing.length ? t("module.missing", { count: missing.length }) : t("module.enabledReady")) : t("module.disabled")}</span>
      </div>
      ${moduleToggle(moduleId)}
    </div>
  `;
}

function moduleToggle(moduleId) {
  return `
    <label class="switch">
      <input type="checkbox" name="${MODULE_SWITCHES[moduleId]}" ${moduleEnabled(moduleId) ? "checked" : ""} />
      <span></span>
    </label>
  `;
}

function field(name, options = {}) {
  const meta = FIELD_META[name] || { label: name };
  const label = meta.label?.startsWith("field.") ? t(meta.label) : meta.label || name;
  const required = options.required ?? (meta.requiredWhen ? moduleEnabled(meta.requiredWhen) : false);
  const value = getValue(name);
  const secretValue = meta.secret && value;
  const inputType = meta.secret ? "password" : meta.type || "text";
  return `
    <label class="field ${required ? "required" : ""}">
      <span>${label}${required ? " <b>*</b>" : ""}</span>
      <input
        name="${name}"
        type="${inputType}"
        ${required ? "required" : ""}
        value="${secretValue ? "" : escapeAttr(value)}"
        placeholder="${secretValue ? t("configuredReplace") : escapeAttr(meta.placeholder || "")}"
      />
      <small>${name}</small>
    </label>
  `;
}

function agentPanel(agent) {
  return `
    <div class="agent-panel">
      <div class="agent-panel-head">
        <div>
          <h3>${escapeHtml(agent.name)}</h3>
          <p>${agent.has_config ? t("existingConfig") : t("newConfig")} · ${agent.caller.gateway_token_configured || agent.matrix.access_token_configured ? t("existingTokenFile") : t("newTokenFile")}</p>
        </div>
        <button type="button" class="secondary danger" id="removeAgent">${t("remove")}</button>
      </div>
      <div class="form-grid">
        ${agentField("Gateway Token", "caller.gateway_token", agent.caller.gateway_token_configured, true)}
        ${agentField("Matrix Access Token", "matrix.access_token", agent.matrix.access_token_configured, true)}
        ${agentTextField("Matrix Account", "matrix.account", agent.matrix.account || agent.name, true)}
        <label class="field inline-check">
          <span>${t("sharedArtifactRead")}</span>
          <input type="checkbox" data-agent-field="caller.shared_artifact_read" ${agent.caller.shared_artifact_read ? "checked" : ""} />
        </label>
      </div>
      <div class="tool-checks">
        <strong>${t("highRiskTools")}</strong>
        ${["matrix_send_text", "matrix_send_image", "matrix_send_audio"].map((tool) => `
          <label>
            <input type="checkbox" data-tool="${tool}" ${agent.high_risk_tools.includes(tool) ? "checked" : ""} />
            <span>${tool}</span>
          </label>
        `).join("")}
      </div>
    </div>
  `;
}

function agentField(label, path, configured, required) {
  return `
    <label class="field ${required && !configured ? "required" : ""}">
      <span>${label}${required ? " <b>*</b>" : ""}</span>
      <input type="password" data-agent-field="${path}" placeholder="${configured ? t("configuredReplace") : t("required")}" ${required && !configured ? "required" : ""} />
      <small>${configured ? t("configured") : t("notConfigured")}</small>
    </label>
  `;
}

function agentTextField(label, path, value, required) {
  return `
    <label class="field ${required ? "required" : ""}">
      <span>${label}${required ? " <b>*</b>" : ""}</span>
      <input type="text" data-agent-field="${path}" value="${escapeAttr(value)}" ${required ? "required" : ""} />
    </label>
  `;
}

function environmentRows() {
  const env = lastStatus.environment || {};
  const rows = [
    ["Python", env.python?.available, env.python?.output || "-"],
    ["PowerShell", env.powershell?.available, env.powershell?.output || "-"],
    ["Config main", env.config_main?.exists, env.config_main?.path],
    ["Config user", env.config_user?.exists, env.config_user?.path],
    ["Agent config", env.agent_config_dir?.exists, env.agent_config_dir?.path],
    ["Artifacts", env.artifact_root?.exists, env.artifact_root?.path],
    ["Database", env.database_path?.exists, env.database_path?.path],
  ];
  return rows.map(([label, ok, detail]) => `
    <div class="check-row">
      <span class="status-dot ${ok ? "ok" : "warn"}"></span>
      <strong>${label}</strong>
      <span>${escapeHtml(detail || "-")}</span>
    </div>
  `).join("");
}

function statusFact(label, value, tone) {
  return `<div class="status-fact ${tone}"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function emptyState(title, body) {
  return `<div class="empty-state"><strong>${title}</strong><p>${body}</p></div>`;
}

function actionBar(label) {
  return `
    <div class="action-bar">
      <button type="button" class="secondary" id="reloadDraft">${t("reload")}</button>
      <button type="submit">${label}</button>
    </div>
  `;
}

function attachDynamicHandlers() {
  $("#reloadDraft")?.addEventListener("click", () => loadStatus(false));
  document.querySelectorAll("[name]").forEach((input) => {
    input.addEventListener("input", () => {
      input.classList.toggle("invalid", input.required && !input.value.trim());
    });
    input.addEventListener("change", () => {
      if (Object.values(MODULE_SWITCHES).includes(input.name)) {
        updateLocalField(input.name, input.checked ? "true" : "false");
        renderAll();
      }
    });
  });
  $("#workflowSelect")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-workflow]");
    if (!button) return;
    applyWorkflow(button.dataset.workflow);
    renderPage();
  });
  document.querySelectorAll(".agent-tab").forEach((button) => {
    button.addEventListener("click", () => {
      saveActiveAgentDraft();
      activeAgent = button.dataset.agent;
      renderPage();
    });
  });
  $("#addAgent")?.addEventListener("click", addAgent);
  $("#removeAgent")?.addEventListener("click", removeActiveAgent);
  document.querySelectorAll("[data-agent-field], [data-tool]").forEach((input) => {
    input.addEventListener("input", saveActiveAgentDraft);
    input.addEventListener("change", saveActiveAgentDraft);
  });
}

function updateLocalField(name, value) {
  lastStatus.webui.owned_fields = { ...(lastStatus.webui.owned_fields || {}), [name]: value };
}

function applyWorkflow(id) {
  const workflow = WORKFLOWS[id] || WORKFLOWS.custom;
  if (workflow.path) updateLocalField("LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH", workflow.path);
  Object.entries(workflow.defaults || {}).forEach(([key, value]) => updateLocalField(key, value));
}

function inferWorkflow() {
  const path = getValue("LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH");
  if (path === WORKFLOWS.sdxl.path) return "sdxl";
  if (path === WORKFLOWS.anima.path) return "anima";
  return "custom";
}

function workflowLabel(id, workflow) {
  if (id === "custom") return language() === "zh-CN" ? "自定义" : "Custom";
  return workflow.label;
}

function addAgent() {
  saveActiveAgentDraft();
  const name = window.prompt(t("agentNamePrompt"));
  const cleaned = (name || "").trim();
  if (!cleaned) return;
  if (!/^[A-Za-z0-9_-]+$/.test(cleaned)) {
    showMessage(t("agentNameInvalid"), "danger");
    return;
  }
  if (draftAgents.some((agent) => agent.name === cleaned)) {
    activeAgent = cleaned;
    renderPage();
    return;
  }
  draftAgents.push({
    name: cleaned,
    enabled: true,
    has_config: false,
    has_env: false,
    caller: {
      role: "role_play",
      shared_artifact_read: false,
      gateway_token_configured: false,
      gateway_token: "",
    },
    matrix: {
      enabled: true,
      account: cleaned,
      access_token_configured: false,
      access_token: "",
    },
    high_risk_tools: ["matrix_send_text", "matrix_send_image", "matrix_send_audio"],
  });
  activeAgent = cleaned;
  renderPage();
}

function removeActiveAgent() {
  if (!activeAgent) return;
  draftAgents = draftAgents.filter((agent) => agent.name !== activeAgent);
  activeAgent = draftAgents[0]?.name || null;
  renderPage();
}

function saveActiveAgentDraft() {
  if (!activeAgent) return;
  const agent = draftAgents.find((item) => item.name === activeAgent);
  if (!agent) return;
  document.querySelectorAll("[data-agent-field]").forEach((input) => {
    const value = input.type === "checkbox" ? input.checked : input.value.trim();
    setDeep(agent, input.dataset.agentField, value);
  });
  agent.high_risk_tools = Array.from(document.querySelectorAll("[data-tool]:checked")).map((input) => input.dataset.tool);
}

async function saveConfig(event) {
  event.preventDefault();
  saveActiveAgentDraft();
  const invalid = Array.from(document.querySelectorAll("input[required]")).filter((input) => !input.value.trim());
  invalid.forEach((input) => input.classList.add("invalid"));
  if (invalid.length) {
    showMessage(t("fillRequired"), "danger");
    invalid[0].focus();
    return;
  }
  const owned = collectOwnedFields();
  const body = { owned_fields: owned };
  if (currentPage === "matrix" || currentPage === "dashboard") {
    body.agents = draftAgents;
  }
  const response = await fetch("/admin/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    showMessage(payload.error || response.statusText, "danger");
    return;
  }
  showMessage(t("saved"), "success");
  await loadStatus(false);
}

function collectOwnedFields() {
  const owned = { ...(lastStatus?.webui?.owned_fields || {}) };
  document.querySelectorAll("#configForm input[name]").forEach((input) => {
    if (input.type === "password" && !input.value.trim()) return;
    owned[input.name] = input.type === "checkbox" ? (input.checked ? "true" : "false") : input.value.trim() || owned[input.name] || "";
  });
  Object.values(MODULE_SWITCHES).forEach((envName) => {
    const input = document.querySelector(`[name="${envName}"]`);
    if (input) owned[envName] = input.checked ? "true" : "false";
  });
  return owned;
}

function requiredMissing(moduleId) {
  return Object.entries(FIELD_META)
    .filter(([, meta]) => meta.requiredWhen === moduleId)
    .filter(([name]) => !String(getValue(name) || "").trim())
    .map(([name]) => name);
}

function normalizeAgents(agents) {
  return agents.map((agent) => ({
    name: agent.name,
    enabled: agent.enabled !== false,
    has_config: !!agent.has_config,
    caller: {
      role: agent.caller?.role || "role_play",
      shared_artifact_read: !!agent.caller?.shared_artifact_read,
      gateway_token_configured: !!agent.caller?.gateway_token_configured,
      gateway_token: "",
    },
    matrix: {
      enabled: agent.matrix?.enabled !== false,
      account: agent.matrix?.account || agent.name,
      access_token_configured: !!agent.matrix?.access_token_configured,
      access_token: "",
    },
    high_risk_tools: agent.high_risk_tools || [],
  }));
}

function setDeep(target, path, value) {
  const keys = path.split(".");
  let current = target;
  for (const key of keys.slice(0, -1)) {
    current[key] ||= {};
    current = current[key];
  }
  current[keys[keys.length - 1]] = value;
}

function showMessage(text, tone = "neutral") {
  const node = $("#message");
  node.textContent = text;
  node.className = `message ${tone}`;
  node.hidden = false;
}

function normalizeBool(value) {
  return ["1", "true", "yes", "on"].includes(String(value || "").toLowerCase());
}

function applyTheme() {
  const theme = localStorage.getItem("webui.theme") || "system";
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

init();
