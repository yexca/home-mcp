const MODULE_IDS = ["dashboard", "settings", "llm", "image", "localimage", "tts", "matrix", "printer"];

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
  IMAGE_MODEL_ID: { label: "field.model", requiredWhen: "image" },
  IMAGE_TOTAL_TIMEOUT_SECONDS: { label: "field.totalTimeout", type: "number" },
  IMAGE_PROVIDER_TIMEOUT_SECONDS: { label: "field.providerTimeout", type: "number" },
  IMAGE_MAX_DOWNLOAD_BYTES: { label: "field.maxDownloadBytes", type: "number" },

  LOCAL_IMAGE_COMFYUI_BASE_URL: { label: "field.comfyBaseUrl", requiredWhen: "localimage", placeholder: "http://127.0.0.1:8188" },
  LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS: { label: "field.allowedHost", requiredWhen: "localimage", multiline: true },
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
  PRINTER_ALLOWED_PRINTERS: { label: "field.allowedPrinters", requiredWhen: "printer", multiline: true },
  PRINTER_MAX_COPIES: { label: "field.maxCopies", type: "number" },
  PRINTER_MAX_FILE_BYTES: { label: "field.maxFileBytes", type: "number" },
  PRINTER_BRIDGE_TIMEOUT_SECONDS: { label: "field.bridgeTimeout", type: "number" },
};

const MODULE_REQUIRED_FIELDS = {
  image: ["IMAGE_MODEL_ID"],
  localimage: [
    "LOCAL_IMAGE_COMFYUI_BASE_URL",
    "LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS",
    "LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH",
    "LOCAL_IMAGE_DEFAULT_SIZE",
    "LOCAL_IMAGE_DEFAULT_QUALITY",
    "LOCAL_IMAGE_DEFAULT_STYLE",
    "LOCAL_IMAGE_DEFAULT_OUTPUT_FORMAT",
  ],
  tts: ["TTS_LOCAL_HTTP_URL"],
  matrix: ["MATRIX_HOMESERVER"],
  printer: ["PRINTER_BRIDGE_URL", "PRINTER_ALLOWED_PRINTERS"],
};

const STRINGS = {
  "zh-CN": {
    brandSubtitle: "gateway console",
    connected: "已连接",
    disconnected: "未连接",
    connect: "连接",
    adminToken: "登录密钥",
    adminTokenPlaceholder: "HOME_MCP_LOGIN_KEY 环境变量配置的密钥",
    footerHint: "额度、权限、文件和工具参数保存后立即生效；仅模块开关需要重启服务。",
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
    requiredMissing: "当前有必填项未填写，请填写相关配置后再尝试。",
    savedWithDisabledModules: "当前有必填项未填写，已保存当前内容，但未开启配置不完整的模块。",
    saved: "已保存配置，立即生效。模块开关变化需要重启服务。",
    agentNamePrompt: "请输入 agent 名称，只能包含字母、数字、下划线和连字符。",
    agentNameInvalid: "agent 名称只能包含字母、数字、下划线和连字符。",
    sharedArtifactRead: "共享 artifact 读取",
    agentEnabled: "启用 agent",
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
      settings: { label: "全局设置", title: "额度与全局设置", kicker: "Limits & Settings" },
      llm: { label: "LLM 管理", title: "模型管理", kicker: "Providers & Models" },
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
      allowedPrinters: "允许打印机",
    },
    empty: {
      title: "连接后显示配置",
      body: "输入环境变量配置的登录密钥后进入管理界面。",
    },
  },
  en: {
    brandSubtitle: "gateway console",
    connected: "Connected",
    disconnected: "Disconnected",
    connect: "Connect",
    adminToken: "Login key",
    adminTokenPlaceholder: "Key configured in HOME_MCP_LOGIN_KEY",
    footerHint: "Quotas, permissions, artifacts and tool parameters apply on save. Only module switches require restart.",
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
    requiredMissing: "Required fields are missing. Fill the related config, then try again.",
    savedWithDisabledModules: "Required fields are missing. Saved the current values, but left incomplete modules disabled.",
    saved: "Configuration saved and applied immediately. Module switch changes require restart.",
    agentNamePrompt: "Enter an agent name. Use only letters, numbers, underscores, and hyphens.",
    agentNameInvalid: "Agent names may contain only letters, numbers, underscores, and hyphens.",
    sharedArtifactRead: "Shared artifact read",
    agentEnabled: "Enable agent",
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
      settings: { label: "Settings", title: "Limits & Global Settings", kicker: "Limits & Settings" },
      llm: { label: "LLM Management", title: "Model Management", kicker: "Providers & Models" },
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
      allowedPrinters: "Allowed printers",
    },
    empty: {
      title: "Connect To Show Config",
      body: "Enter the login key configured in the environment to open management.",
    },
  },
};

// UI copy is kept together so every new flow works in both languages.
Object.assign(STRINGS["zh-CN"], {
  ui: {
    skip: "跳转到内容", workspace: "工作空间", localGateway: "本地网关", sidebarHint: "连接工具，让协作发生。",
    welcome: "连接你的工作空间", remember: "在此设备记住 Token", tokenHint: "Token 默认仅在当前标签页会话中保留。",
    overview: "网关概览", overviewDesc: "工具、连接与运行状态，尽在一处。",
    welcomeBack: "你的工具，从这里连接。", bannerDesc: "管理 MCP 模块，为每一次协作准备好工具。",
    runtimeModules: "运行中模块", runtimeHint: "当前服务已加载", configuredModules: "配置中启用", configuredHint: "保存并重启后生效",
    agents: "已启用 Agent", agentHint: "当前配置中的协作身份", checks: "环境检查", checksHint: "运行依赖检查通过",
    modulesTitle: "工具模块", modulesDesc: "按需启用，点击配置完善连接信息。", configure: "配置", configuration: "连接配置",
    guideTitle: "从一个模块开始", guideDesc: "填写连接信息，启用模块并保存。重启网关后，就能在 MCP 客户端中使用。",
    environment: "运行环境", environmentDesc: "配置文件与本地运行依赖", serviceInfo: "网关信息", serviceDesc: "当前连接的服务",
    runtime: "运行中", stopped: "未运行", pendingRestart: "开关待重启", ready: "配置完整", incomplete: "待完善",
    enabled: "已启用", disabled: "未启用", enable: "启用 {name}", refresh: "刷新状态", disconnect: "断开",
    connecting: "连接中…", refreshing: "刷新中…", saving: "保存中…", saveAll: "保存全部更改",
    savedState: "所有更改已保存", cleanState: "配置与服务器同步", changes: "{count} 项未保存更改",
    saveHint: "草稿在页面间保留 · 保存配置后，重启服务生效", discard: "放弃更改", cancel: "取消", confirm: "确认",
    discardTitle: "放弃未保存的更改？", discardDesc: "所有模块和 Agent 的草稿将恢复为上次载入或保存的内容。",
    refreshTitle: "重新载入服务器配置？", refreshDesc: "当前未保存的更改将被服务器配置替换。",
    disconnectTitle: "断开当前连接？", disconnectDesc: "未保存的草稿将被清除。", disconnectedMessage: "已断开连接，并清除此设备保存的 Token。",
    show: "显示", hide: "隐藏", close: "关闭", tokenRequired: "请输入 Admin Token。", sessionExpired: "身份验证失败，请检查 Admin Token 或重新连接。",
    requestFailed: "请求失败，请检查服务是否可用。", timeout: "请求超时，请稍后重试。",
    saveFailed: "保存失败：{message}", savedRefreshFailed: "配置已保存，但刷新状态失败。请稍后刷新，勿重复提交。",
    validation: "有 {count} 项配置需要完善", validationHint: "更改尚未保存。点击下面的字段前往修改，或关闭暂不使用的模块。",
    missingField: "请填写此字段", invalidNumber: "请输入大于 0 的有效数字", invalidInteger: "请输入大于 0 的整数", invalidUrl: "请输入有效的 http:// 或 https:// 地址",
    connection: "连接信息", connectionDesc: "设置服务地址与访问凭据。", advanced: "高级设置", advancedDesc: "超时与资源限制",
    moduleGuide: "配置小贴士", stepOne: "填写服务地址和所需凭据", stepTwo: "打开模块开关并保存全部更改", stepThree: "重启网关，使配置生效",
    disabledNote: "模块关闭时也可以保存配置。准备好后再启用。",
    imageDesc: "通过兼容 OpenAI 的接口生成与编辑图片。", localimageDesc: "连接 ComfyUI，运行本地图片生成工作流。",
    ttsDesc: "连接语音服务，将文字转为音频。", matrixDesc: "配置消息服务与 Agent 的独立身份。", printerDesc: "连接打印桥接服务，管理允许使用的打印机。",
    workflow: "工作流与模型", workflowDesc: "选择模板后填写对应的模型名称。", workflowTitle: "应用工作流模板？",
    workflowConfirm: "切换模板会替换工作流路径和模型名称，其他配置会保留。", defaults: "默认生成参数",
    addAgent: "添加 Agent", agentName: "Agent 名称", agentDuplicate: "此名称已存在，请换一个名称。",
    removeAgent: "移除 Agent「{name}」？", removeAgentDesc: "保存后，此 Agent 将从启用列表中移除，WebUI 管理的配置文件也会删除。",
    newAgentDesc: "名称可包含字母、数字、下划线和连字符。创建后填写访问凭据。",
    permissions: "工具权限", noAgentBody: "添加一个 Agent，为它设置独立的访问凭据和消息权限。",
    draftSecret: "已填写新值，保存后替换", configuredSecret: "已配置 · 留空保留原值", copied: "已复制",
    configPath: "配置文件", address: "监听地址", version: "版本", service: "服务", exists: "可用", missing: "待检查",
    navigate: "前往 {name}", agentError: "Agent {name}：{field}", needsRestart: "配置已保存；重启服务后生效。"
  }
});
Object.assign(STRINGS.en, {
  ui: {
    skip: "Skip to content", workspace: "WORKSPACE", localGateway: "Local gateway", sidebarHint: "Your tools, connected.",
    welcome: "Connect your workspace", remember: "Remember token on this device", tokenHint: "By default, your token stays in this tab's session only.",
    overview: "Gateway overview", overviewDesc: "Your tools, connections, and runtime. All in one place.",
    welcomeBack: "A home for all your tools.", bannerDesc: "Manage your MCP modules and get ready for your next collaboration.",
    runtimeModules: "Running modules", runtimeHint: "Loaded by the current service", configuredModules: "Enabled in config", configuredHint: "Apply with save and restart",
    agents: "Enabled agents", agentHint: "Identities in your configuration", checks: "Environment checks", checksHint: "Runtime dependencies available",
    modulesTitle: "Tool modules", modulesDesc: "Enable what you need. Configure each connection to get started.", configure: "Configure", configuration: "Connection settings",
    guideTitle: "Start with one module", guideDesc: "Add a connection, enable the module, and save. Restart the gateway to use it in your MCP client.",
    environment: "Environment", environmentDesc: "Configuration files and local dependencies", serviceInfo: "Gateway details", serviceDesc: "Your connected service",
    runtime: "Running", stopped: "Not running", pendingRestart: "Restart pending", ready: "Configured", incomplete: "Needs setup",
    enabled: "Enabled", disabled: "Disabled", enable: "Enable {name}", refresh: "Refresh", disconnect: "Disconnect",
    connecting: "Connecting…", refreshing: "Refreshing…", saving: "Saving…", saveAll: "Save all changes",
    savedState: "All changes saved", cleanState: "Configuration is up to date", changes: "{count} unsaved changes",
    saveHint: "Drafts stay across pages · Restart the service after saving", discard: "Discard changes", cancel: "Cancel", confirm: "Confirm",
    discardTitle: "Discard unsaved changes?", discardDesc: "All module and agent drafts will return to the last loaded or saved configuration.",
    refreshTitle: "Reload server configuration?", refreshDesc: "Your unsaved changes will be replaced with the server configuration.",
    disconnectTitle: "Disconnect this session?", disconnectDesc: "Your unsaved drafts will be cleared.", disconnectedMessage: "Disconnected. Saved tokens have been removed from this device.",
    show: "Show", hide: "Hide", close: "Close", tokenRequired: "Enter an Admin Token.", sessionExpired: "Authentication failed. Check your Admin Token or reconnect.",
    requestFailed: "Request failed. Check that the service is available.", timeout: "The request timed out. Please try again.",
    saveFailed: "Could not save: {message}", savedRefreshFailed: "Configuration saved, but status refresh failed. Refresh later; do not submit again.",
    validation: "{count} configuration issues", validationHint: "Changes have not been saved. Select a field below to fix it, or disable modules you are not using.",
    missingField: "Fill in this field", invalidNumber: "Enter a number greater than 0", invalidInteger: "Enter a positive integer", invalidUrl: "Enter a valid http:// or https:// address",
    connection: "Connection", connectionDesc: "Set the service address and access credentials.", advanced: "Advanced settings", advancedDesc: "Timeouts and resource limits",
    moduleGuide: "Setup notes", stepOne: "Add the service address and required credentials", stepTwo: "Enable the module and save all changes", stepThree: "Restart the gateway to apply your configuration",
    disabledNote: "You can save configuration while a module is disabled. Enable it when you are ready.",
    imageDesc: "Generate and edit images through an OpenAI-compatible API.", localimageDesc: "Run local image workflows with ComfyUI.",
    ttsDesc: "Connect a speech service to turn text into audio.", matrixDesc: "Set up messaging and individual agent identities.", printerDesc: "Connect a print bridge and manage allowed printers.",
    workflow: "Workflow and models", workflowDesc: "Choose a template, then enter the matching model names.", workflowTitle: "Apply workflow template?",
    workflowConfirm: "This replaces the workflow path and model names. Other settings will be kept.", defaults: "Generation defaults",
    addAgent: "Add agent", agentName: "Agent name", agentDuplicate: "This name already exists. Choose another name.",
    removeAgent: "Remove agent “{name}”?", removeAgentDesc: "After saving, this agent will leave the enabled list and its WebUI-managed configuration files will be deleted.",
    newAgentDesc: "Use letters, numbers, underscores, and hyphens. Add access credentials after creating the agent.",
    permissions: "Tool permissions", noAgentBody: "Add an agent with its own credentials and messaging permissions.",
    draftSecret: "New value entered; will replace on save", configuredSecret: "Configured · Leave blank to keep", copied: "Copied",
    configPath: "Config file", address: "Listen address", version: "Version", service: "Service", exists: "Available", missing: "Check needed",
    navigate: "Go to {name}", agentError: "Agent {name}: {field}", needsRestart: "Configuration saved. Restart the service to apply."
  }
});

const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
  localimage: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  tts: '<path d="M4 10v4m4-8v12m4-15v18m4-15v12m4-8v4"/>',
  matrix: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5A8.5 8.5 0 0 1 10.5 3h2a8.5 8.5 0 0 1 8.5 8.5Z"/><path d="M7 9h9M7 13h6"/>',
  printer: '<path d="M7 8V3h10v5M7 17H4V8h16v9h-3"/><path d="M7 14h10v7H7zM16 11h1"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  settings: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>'
};
const $ = (selector) => document.querySelector(selector);
const clone = (value) => JSON.parse(JSON.stringify(value));
const icon = (name) => '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || ICONS.settings) + '</svg>';
let lastStatus = null;
let currentPage = "dashboard";
let draftFields = {};
let draftAgents = [];
let baselineAgents = [];
let activeAgent = null;
let workflowSelection = null;
let errors = [];
let busy = "";
let authenticated = false;
let savedNotice = false;
let dialogResolve = null;
let dialogValidate = null;
let devMode = false;
let activeProvider = null;
let providerDrafts = {};
let modelDrafts = {};
let modelSearch = "";

function llmText(zh, en) { return language() === "zh-CN" ? zh : en; }
function metadata(name) {
  const spec = lastStatus?.settings_schema?.[name];
  return spec ? { ...spec, secret: spec.type === "secret", multiline: ["list", "json"].includes(spec.type), kind: spec.type, type: ["number", "integer"].includes(spec.type) ? "number" : "text" } : FIELD_META[name] || {};
}
function hasUnsaved() { return changeCount() > 0 || llmChangeCount() > 0; }

function storageGet(storage, key) { try { return storage.getItem(key); } catch { return null; } }
function storageSet(storage, key, value) { try { value == null ? storage.removeItem(key) : storage.setItem(key, value); } catch { /* Private browsing may disable storage. */ } }
function language() {
  const saved = storageGet(localStorage, "webui.language");
  return STRINGS[saved] ? saved : navigator.language.toLowerCase().startsWith("zh") ? "zh-CN" : "en";
}
function t(key, vars = {}) {
  const lookup = (root) => key.split(".").reduce((value, part) => value?.[part], root);
  return Object.entries(vars).reduce((text, [name, value]) => text.replaceAll("{" + name + "}", String(value)), String(lookup(STRINGS[language()]) ?? lookup(STRINGS.en) ?? key));
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])); }
const escapeAttr = escapeHtml;
function normalizeBool(value) { return ["1", "true", "yes", "on"].includes(String(value || "").toLowerCase()); }
function getValues() { return { ...lastStatus?.local_env, ...lastStatus?.webui?.owned_fields, ...draftFields }; }
function getValue(name) { return String(getValues()[name] ?? ""); }
function moduleEnabled(id) { return normalizeBool(getValue(MODULE_SWITCHES[id])); }
function agentsChanged() { return JSON.stringify(draftAgents) !== JSON.stringify(baselineAgents); }
function changeCount() {
  const changedNames = new Set([...draftAgents, ...baselineAgents].map((agent) => agent.name));
  let count = Object.keys(draftFields).length;
  changedNames.forEach((name) => {
    if (JSON.stringify(draftAgents.find((agent) => agent.name === name)) !== JSON.stringify(baselineAgents.find((agent) => agent.name === name))) count++;
  });
  return count;
}
function updateLocalField(name, value) {
  const baseline = { ...lastStatus?.local_env, ...lastStatus?.webui?.owned_fields };
  if ((metadata(name).secret && !value) || value === String(baseline[name] ?? "")) delete draftFields[name];
  else draftFields[name] = value;
  savedNotice = false;
}
function init() {
  storageSet(localStorage, "webui.adminToken", null);
  storageSet(sessionStorage, "webui.adminToken", null);
  $("#adminToken").value = storageGet(sessionStorage, "webui.loginKey") || "";
  $("#authForm").addEventListener("submit", (event) => { event.preventDefault(); loadStatus(); });
  $("#configForm").addEventListener("submit", saveConfig);
  $("#refreshStatus").addEventListener("click", refreshStatus);
  $("#discardDraft").addEventListener("click", discardDraft);
  $("#disconnect").addEventListener("click", disconnect);
  $("#dismissMessage").addEventListener("click", () => { $("#message").hidden = true; });
  $("#themeSelect").addEventListener("change", (event) => { storageSet(localStorage, "webui.theme", event.target.value); applyTheme(); });
  $("#languageSelect").addEventListener("change", (event) => { storageSet(localStorage, "webui.language", event.target.value); errors = []; $("#message").hidden = true; renderAll(); });
  $("#configForm").addEventListener("input", handleInput);
  $("#configForm").addEventListener("change", handleChange);
  $("#configForm").addEventListener("click", handlePageClick);
  document.addEventListener("click", (event) => {
    const reveal = event.target.closest("[data-reveal]");
    if (!reveal) return;
    const input = document.getElementById(reveal.dataset.reveal);
    input.type = input.type === "password" ? "text" : "password";
    reveal.textContent = t(input.type === "password" ? "ui.show" : "ui.hide");
    reveal.setAttribute("aria-pressed", String(input.type === "text"));
  });
  $("#dialogForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = $("#dialogInputLabel").hidden ? true : $("#dialogInput").value.trim();
    const error = dialogValidate?.(value);
    $("#dialogError").textContent = error || "";
    if (error) { $("#dialogInput").focus(); return; }
    closeDialog(value);
  });
  ["#dialogClose", "#dialogCancel"].forEach((id) => $(id).addEventListener("click", () => closeDialog(false)));
  $("#appDialog").addEventListener("cancel", (event) => { event.preventDefault(); closeDialog(false); });
  window.addEventListener("hashchange", () => routeTo(location.hash.slice(1)));
  window.addEventListener("beforeunload", (event) => { if (hasUnsaved() || busy) { event.preventDefault(); event.returnValue = ""; } });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && lastStatus && !$("#appDialog").open) {
      event.preventDefault(); if (currentPage !== "llm" && changeCount() && !busy) saveConfig(event);
    }
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
  applyTheme();
  currentPage = MODULE_IDS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "dashboard";
  renderAll();
  initializeAuth();
}
async function initializeAuth() {
  try {
    const auth = await request("/admin/api/auth");
    authenticated = false;
    devMode = !!auth.dev_mode;
    if (devMode || $("#adminToken").value) await loadStatus(false);
    else if (!auth.login_configured) showMessage(llmText("请设置 HOME_MCP_LOGIN_KEY，或通过 HOME_MCP_DEV_MODE=true 启用开发模式。", "Set HOME_MCP_LOGIN_KEY, or enable HOME_MCP_DEV_MODE=true."), "warning");
  } catch (error) { showMessage(error.message, "danger"); }
}
function applyTheme() {
  const theme = storageGet(localStorage, "webui.theme") || "system";
  document.documentElement.dataset.theme = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
}
function applyStaticI18n() {
  document.documentElement.lang = language();
  document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
  $("#languageSelect").value = language();
  $("#themeSelect").value = storageGet(localStorage, "webui.theme") || "system";
  ["themeSystem", "themeLight", "themeDark"].forEach((key, index) => { $("#themeSelect").options[index].textContent = t(key); });
  $("#adminToken").placeholder = t("adminTokenPlaceholder");
  $("#dismissMessage").setAttribute("aria-label", t("ui.close"));
  $("#dialogClose").setAttribute("aria-label", t("ui.close"));
  document.querySelectorAll("[data-reveal]").forEach((button) => {
    const input = document.getElementById(button.dataset.reveal);
    button.textContent = t(input.type === "password" ? "ui.show" : "ui.hide");
    button.setAttribute("aria-label", t(input.type === "password" ? "ui.show" : "ui.hide") + " " + (input.getAttribute("aria-label") || t("adminToken")));
    button.setAttribute("aria-pressed", String(input.type === "text"));
  });
}
function updateChrome() {
  $("#pageTitle").textContent = currentPage === "dashboard" ? t("ui.overview") : t("modules." + currentPage + ".title");
  $("#pageKicker").textContent = currentPage === "dashboard" ? t("ui.overview") : t("modules." + currentPage + ".label");
  $("#pageDescription").textContent = t(currentPage === "dashboard" ? "ui.overviewDesc" : "ui." + currentPage + "Desc");
  $("#runtimeBadge").innerHTML = '<span class="status-dot ' + (authenticated ? "ok" : "") + '"></span>' + t(authenticated ? "connected" : "disconnected");
  $("#runtimeBadge").className = "status-pill " + (authenticated ? "success" : "muted");
  $("#restartBadge").hidden = !lastStatus?.restart_required;
  $("#restartBadge").textContent = t("ui.pendingRestart");
  $("#authPanel").hidden = !!lastStatus;
  $("#configForm").hidden = !lastStatus;
  $("#saveBar").hidden = !lastStatus || currentPage === "llm";
  $("#refreshStatus").hidden = !lastStatus;
  $("#disconnect").hidden = !lastStatus || devMode;
  $("#refreshStatus").textContent = t(busy === "load" ? "ui.refreshing" : "ui.refresh");
  $("#disconnect").textContent = t("ui.disconnect");
  $("#loadStatus").textContent = t(busy === "load" ? "ui.connecting" : "connect");
  $("#snapshotInfo").textContent = lastStatus ? t("ui.configPath") + ": " + (lastStatus.webui?.active_snapshot || "—") : "LOCAL MCP GATEWAY";
  $("#serverVersion").textContent = lastStatus?.server?.version || "";
  updateDraftBar();
}
function updateDraftBar() {
  const count = changeCount();
  $("#dirtyInfo").textContent = count ? t("ui.changes", { count }) : t(savedNotice ? "ui.savedState" : "ui.cleanState");
  $("#draftDot").className = "status-dot " + (count ? "warn" : "ok");
  $("#discardDraft").textContent = t("ui.discard");
  $("#saveConfig").textContent = t(busy === "save" ? "ui.saving" : "ui.saveAll");
  $("#saveConfig").disabled = !!busy || !count;
  $("#discardDraft").disabled = !!busy || !count;
  $("#configFields").disabled = !!busy;
  $("#configForm").setAttribute("aria-busy", String(!!busy));
  ["#refreshStatus", "#disconnect", "#loadStatus", "#adminToken"].forEach((id) => { $(id).disabled = !!busy; });
}
function renderAll() {
  const focusedId = document.activeElement?.id;
  renderNav(); renderPage(); applyStaticI18n(); updateChrome();
  if (focusedId) document.getElementById(focusedId)?.focus({ preventScroll: true });
}
function renderNav() {
  $("#sidebarNav").innerHTML = MODULE_IDS.map((id, index) => {
    const dirty = id !== "dashboard" && (Object.keys(draftFields).some((name) => name === MODULE_SWITCHES[id] || fieldModule(name) === id) || (id === "matrix" && agentsChanged()) || (id === "llm" && llmChangeCount()));
    return (index === 1 ? '<div class="nav-divider"></div>' : "") + '<a class="nav-item ' + (currentPage === id ? "active" : "") + '" href="#' + id + '"' + (currentPage === id ? ' aria-current="page"' : "") + '>' + icon(id) + '<span>' + t(id === "dashboard" ? "ui.overview" : "modules." + id + ".label") + '</span>' + (id !== "dashboard" ? '<span class="mini-dot ' + (dirty ? "dirty" : moduleEnabled(id) ? "on" : "") + '"></span>' : "") + '</a>';
  }).join("");
}
function routeTo(page) {
  if (page === "main") { $("#main").focus(); return; }
  currentPage = MODULE_IDS.includes(page) ? page : "dashboard";
  renderAll();
  window.scrollTo({ top: 0, behavior: "auto" });
}
function acceptStatus(payload, preserveLLM = false) {
  lastStatus = payload; authenticated = true; draftFields = {}; errors = []; workflowSelection = null;
  baselineAgents = normalizeAgents(payload.agents || []); draftAgents = clone(baselineAgents);
  if (!preserveLLM) { providerDrafts = {}; modelDrafts = {}; activeProvider = null; modelSearch = ""; }
  if (!draftAgents.some((agent) => agent.name === activeAgent)) activeAgent = draftAgents[0]?.name || null;
}
async function request(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path.endsWith("/discover") ? 40000 : 15000);
  try {
    const token = $("#adminToken").value.trim();
    const response = await fetch(path, {
      method: body ? "POST" : "GET", signal: controller.signal,
      headers: { Authorization: "Bearer " + token, ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {})
    });
    if (response.status === 401 || response.status === 403) { authenticated = false; throw new Error(t("ui.sessionExpired")); }
    const payload = await response.json().catch(() => { throw new Error(t("ui.requestFailed") + " (HTTP " + response.status + ")"); });
    if (!response.ok || !payload.ok) throw new Error(payload.error || t("ui.requestFailed"));
    authenticated = true;
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new Error(t("ui.timeout"));
    throw error;
  } finally { clearTimeout(timeout); }
}
async function loadStatus(showSuccess = true) {
  if (busy) return;
  if (!devMode && !$("#adminToken").value.trim()) { showMessage(t("ui.tokenRequired"), "danger"); $("#adminToken").focus(); return; }
  busy = "load"; updateChrome();
  try {
    const payload = await request("/admin/api/status");
    acceptStatus(payload); savedNotice = false;
    if (!devMode) storageSet(sessionStorage, "webui.loginKey", $("#adminToken").value.trim());
    if (showSuccess) showMessage(t("statusLoaded"), "success");
  } catch (error) { showMessage(t("loadFailed", { message: error.message }), "danger"); }
  finally { busy = ""; renderAll(); }
}
async function refreshStatus() {
  if (busy) return;
  if (hasUnsaved() && !await openDialog({ title: t("ui.refreshTitle"), description: t("ui.refreshDesc"), confirm: t("ui.refresh") })) return;
  await loadStatus();
}
async function discardDraft() {
  if (busy || !changeCount()) return;
  if (!await openDialog({ title: t("ui.discardTitle"), description: t("ui.discardDesc"), confirm: t("ui.discard") })) return;
  draftFields = {}; draftAgents = clone(baselineAgents); workflowSelection = null; errors = []; savedNotice = false;
  $("#message").hidden = true; renderAll();
}
async function disconnect() {
  if (busy) return;
  if (hasUnsaved() && !await openDialog({ title: t("ui.disconnectTitle"), description: t("ui.disconnectDesc") })) return;
  lastStatus = null; authenticated = false; draftFields = {}; draftAgents = []; baselineAgents = []; errors = [];
  providerDrafts = {}; modelDrafts = {}; activeProvider = null;
  $("#adminToken").value = ""; $("#adminToken").type = "password";
  storageSet(sessionStorage, "webui.loginKey", null);
  showMessage(t("ui.disconnectedMessage")); renderAll(); $("#adminToken").focus();
}
function openDialog({ title, description, confirm = t("ui.confirm"), input = false, validate = null }) {
  $("#dialogTitle").textContent = title; $("#dialogDescription").textContent = description;
  $("#dialogCancel").textContent = t("ui.cancel"); $("#dialogConfirm").textContent = confirm;
  $("#dialogInputLabel").hidden = !input; $("#dialogInput").value = ""; $("#dialogError").textContent = "";
  dialogValidate = validate;
  return new Promise((resolve) => { dialogResolve = resolve; $("#appDialog").showModal(); (input ? $("#dialogInput") : $("#dialogCancel")).focus(); });
}
function closeDialog(value) { $("#appDialog").close(); const resolve = dialogResolve; dialogResolve = null; dialogValidate = null; resolve?.(value); }
function showMessage(message, tone = "neutral") { $("#messageText").textContent = message; $("#message").className = "message " + tone; $("#message").hidden = false; }
function renderPage() {
  const mount = $("#pageMount");
  if (!lastStatus) { mount.innerHTML = ""; return; }
  if (currentPage === "dashboard") mount.innerHTML = renderDashboard();
  else if (currentPage === "settings") mount.innerHTML = renderSettings();
  else if (currentPage === "llm") { mount.innerHTML = renderLLM(); attachLLMHandlers(); }
  else if (currentPage === "localimage") mount.innerHTML = renderLocalImage();
  else if (currentPage === "matrix") mount.innerHTML = renderMatrix();
  else mount.innerHTML = renderModule(currentPage);
  if (MODULE_SWITCHES[currentPage]) {
    const stack = mount.querySelector(".config-stack");
    stack.insertAdjacentHTML("beforeend", settingsGroup(currentPage, t("ui.parameters"), t("ui.parametersDesc"), true) + '<a class="settings-link" href="#settings">' + t("ui.quotas") + ' ' + icon("arrow") + '</a>');
  }
  mount.insertAdjacentHTML("afterbegin", validationSummary());
}
function environmentChecks() {
  const env = lastStatus.environment || {};
  return [
    ["Python", env.python?.available, env.python?.output || "—"],
    ["Config main", env.config_main?.exists, env.config_main?.path],
    ["Config user", env.config_user?.exists, env.config_user?.path],
    ["Agent config", env.agent_config_dir?.exists, env.agent_config_dir?.path],
    ["Artifacts", env.artifact_root?.exists, env.artifact_root?.path],
    ["Database", env.database_path?.exists, env.database_path?.path]
  ];
}
function renderDashboard() {
  const ids = Object.keys(MODULE_SWITCHES), checks = environmentChecks();
  const metric = (name, label, value, hint) => '<div class="metric"><span class="metric-label">' + icon(name) + t(label) + '</span><strong>' + value + '</strong><small>' + t(hint) + '</small></div>';
  const fact = (label, value) => '<div class="fact"><span>' + t(label) + '</span><strong>' + escapeHtml(value || "—") + '</strong></div>';
  return '<section class="overview-banner"><div><div class="eyebrow">YOUR CONNECTED WORKSPACE</div><h2>' + t("ui.welcomeBack") + '</h2><p>' + t("ui.bannerDesc") + '</p></div><div class="banner-icon">' + icon("localimage") + '</div></section>' +
    '<section class="metric-grid" aria-label="' + t("ui.overview") + '">' +
    metric("activity", "ui.runtimeModules", ids.filter((id) => lastStatus.modules?.[id]?.enabled).length + '<span class="metric-denominator"> / 5</span>', "ui.runtimeHint") +
    metric("settings", "ui.configuredModules", ids.filter(moduleEnabled).length + '<span class="metric-denominator"> / 5</span>', "ui.configuredHint") +
    metric("matrix", "ui.agents", draftAgents.filter((agent) => agent.enabled).length, "ui.agentHint") +
    metric("shield", "ui.checks", checks.filter(([, ok]) => ok).length + '<span class="metric-denominator"> / 6</span>', "ui.checksHint") +
    '</section><section><div class="section-heading"><div><h2>' + t("ui.modulesTitle") + '</h2><p>' + t("ui.modulesDesc") + '</p></div><span class="status-pill">5 modules</span></div><div class="module-grid">' +
    ids.map(moduleCard).join("") + '<article class="module-card setup-card">' + icon("info") + '<h3>' + t("ui.guideTitle") + '</h3><p>' + t("ui.guideDesc") + '</p></article></div></section>' +
    '<section class="overview-details"><article class="panel">' + panelHeading(t("ui.environment"), t("ui.environmentDesc")) +
    '<div class="check-list">' + checks.map(([label, ok, detail]) => '<div class="check-row"><span class="status-dot ' + (ok ? "ok" : "warn") + '" aria-label="' + t(ok ? "ui.exists" : "ui.missing") + '"></span><strong>' + label + '</strong><span class="check-detail">' + escapeHtml(detail || "—") + '</span></div>').join("") +
    '</div></article><article class="panel">' + panelHeading(t("ui.serviceInfo"), t("ui.serviceDesc")) + '<div class="facts">' +
    fact("ui.service", lastStatus.server?.name) + fact("ui.version", lastStatus.server?.version) +
    fact("ui.address", lastStatus.server?.host + ":" + lastStatus.server?.port) + fact("ui.configPath", lastStatus.webui?.active_snapshot) +
    '</div></article></section>';
}
function moduleCard(id) {
  const enabled = moduleEnabled(id);
  const pending = enabled !== !!lastStatus.modules?.[id]?.enabled;
  const missing = requiredMissing(id).length;
  return '<article class="module-card"><div class="module-card-top"><span class="module-icon ' + id + '">' + icon(id) + '</span>' + moduleToggle(id) + '</div><h3>' +
    t("modules." + id + ".label") + '</h3><p>' + t("ui." + id + "Desc") + '</p><div class="module-card-bottom"><span class="status-pill ' + (pending || (enabled && missing) ? "warning" : enabled ? "success" : "") + '">' +
    t(enabled && missing ? "ui.incomplete" : pending ? "ui.pendingRestart" : lastStatus.modules?.[id]?.enabled ? "ui.runtime" : "ui.disabled") +
    '</span><a class="module-link" href="#' + id + '" aria-label="' + t("ui.navigate", { name: t("modules." + id + ".label") }) + '">' + t("ui.configure") + icon("arrow") + '</a></div></article>';
}
function panelHeading(title, description, action = "") {
  return '<div class="panel-heading"><div><h2>' + title + '</h2>' + (description ? '<p>' + description + '</p>' : "") + '</div>' + action + '</div>';
}
function moduleToggle(id) {
  return '<label class="switch"><input id="toggle-' + id + '" type="checkbox" name="' + MODULE_SWITCHES[id] + '" aria-label="' + t("ui.enable", { name: t("modules." + id + ".label") }) + '"' + (moduleEnabled(id) ? " checked" : "") + ' /><span class="switch-track"></span></label>';
}
function moduleStatus(id) {
  return '<div class="module-status"><span class="status-pill ' + (moduleEnabled(id) ? "success" : "") + '">' + t(moduleEnabled(id) ? "ui.enabled" : "ui.disabled") + '</span>' + moduleToggle(id) + '</div>';
}
function guide() {
  return '<aside class="aside-note">' + icon("info") + '<h3>' + t("ui.moduleGuide") + '</h3><p>' + t("ui.disabledNote") + '</p>' +
    ["stepOne", "stepTwo", "stepThree"].map((key, i) => '<div class="note-step"><b>' + (i + 1) + '</b><span>' + t("ui." + key) + '</span></div>').join("") + '</aside>';
}
function renderModule(id) {
  const fields = Object.keys(FIELD_META).filter((name) => fieldModule(name) === id);
  const basic = fields.filter((name) => FIELD_META[name].type !== "number");
  const advanced = fields.filter((name) => FIELD_META[name].type === "number");
  return '<div class="config-layout"><div class="config-stack"><section class="panel">' +
    panelHeading(t("ui.connection"), t("ui.connectionDesc"), moduleStatus(id)) +
    '<div class="form-grid">' + basic.map((name) => field(name)).join("") + '</div></section>' +
    advancedPanel(advanced) + '</div>' + guide() + '</div>';
}
function advancedPanel(fields) {
  const hasErrors = errors.some((error) => fields.includes(error.field));
  return '<details class="panel advanced"' + (hasErrors ? " open" : "") + '><summary>' + icon("settings") + t("ui.advanced") + '</summary><div class="form-grid">' + fields.map((name) => field(name, { technical: true })).join("") + '</div></details>';
}
function inferWorkflow() {
  if (workflowSelection) return workflowSelection;
  const path = getValue("LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH");
  return Object.keys(WORKFLOWS).find((id) => id !== "custom" && WORKFLOWS[id].path === path) || "custom";
}
function workflowLabel(id) { return id === "custom" && language() === "zh-CN" ? "自定义" : WORKFLOWS[id].label; }
function renderLocalImage() {
  const selected = inferWorkflow();
  return '<div class="config-layout"><div class="config-stack"><section class="panel">' +
    panelHeading("ComfyUI", t("ui.connectionDesc"), moduleStatus("localimage")) +
    '<div class="form-grid">' + ["LOCAL_IMAGE_COMFYUI_BASE_URL", "LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS"].map((name) => field(name)).join("") + '</div></section>' +
    '<section class="panel">' + panelHeading(t("ui.workflow"), t("ui.workflowDesc")) +
    '<div class="segmented" role="group" aria-label="' + t("ui.workflow") + '">' +
    Object.keys(WORKFLOWS).map((id) => '<button type="button" data-workflow="' + id + '" aria-pressed="' + (id === selected) + '" class="' + (id === selected ? "selected" : "") + '">' + workflowLabel(id) + '</button>').join("") +
    '</div><div class="form-grid">' + field("LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH", { wide: true }) +
    WORKFLOWS[selected].fields.map((name) => field(name, { required: selected !== "custom" })).join("") + '</div></section>' +
    '<section class="panel">' + panelHeading(t("ui.defaults"), "") + '<div class="form-grid">' +
    ["LOCAL_IMAGE_DEFAULT_SIZE", "LOCAL_IMAGE_DEFAULT_QUALITY", "LOCAL_IMAGE_DEFAULT_STYLE", "LOCAL_IMAGE_DEFAULT_OUTPUT_FORMAT"].map((name) => field(name)).join("") +
    '</div></section>' + advancedPanel(["LOCAL_IMAGE_COMFYUI_TIMEOUT_SECONDS", "LOCAL_IMAGE_COMFYUI_POLL_INTERVAL_SECONDS", "LOCAL_IMAGE_COMFYUI_MAX_WAIT_SECONDS"]) +
    '</div>' + guide() + '</div>';
}
function fieldModule(name) {
  const group = lastStatus?.settings_schema?.[name]?.group;
  if (group) return MODULE_SWITCHES[group] ? group : "settings";
  if (name.startsWith("LOCAL_IMAGE_")) return "localimage";
  return Object.keys(MODULE_SWITCHES).find((id) => name.startsWith(id.toUpperCase() + "_"));
}
function fieldLabel(name) {
  const spec = lastStatus?.settings_schema?.[name];
  if (spec) return llmText(spec.zh, spec.en);
  const label = FIELD_META[name]?.label || name;
  return label.startsWith("field.") ? t(label) : label;
}
function field(name, options = {}) {
  if (name === "IMAGE_MODEL_ID") return imageModelField();
  const meta = metadata(name);
  const required = options.required ?? (MODULE_REQUIRED_FIELDS[fieldModule(name)] || []).includes(name);
  const baseline = { ...lastStatus.local_env, ...lastStatus.webui?.owned_fields };
  const value = meta.secret ? draftFields[name] || "" : getValue(name);
  const configured = meta.secret && !!baseline[name];
  const error = errors.find((item) => !item.agent && item.field === name);
  const label = fieldLabel(name), id = "field-" + name;
  const attrs = ' id="' + id + '" name="' + name + '" aria-label="' + escapeAttr(label) + '" aria-describedby="hint-' + name + (error ? " error-" + name : "") + '" ' +
    (required && moduleEnabled(fieldModule(name)) && !configured ? "required " : "") +
    (error ? 'class="invalid" aria-invalid="true" ' : "") +
    'placeholder="' + escapeAttr(configured ? t("configuredReplace") : meta.placeholder || "") + '"';
  const input = meta.kind === "boolean" ? '<input' + attrs + ' type="checkbox"' + (normalizeBool(value) ? ' checked' : '') + ' />' : meta.multiline ? '<textarea' + attrs + '>' + escapeHtml(value) + '</textarea>' :
    '<input' + attrs + ' type="' + (meta.secret ? "password" : meta.type || "text") + '" value="' + escapeAttr(value) + '"' +
    (meta.secret ? ' autocomplete="new-password" data-secret="true"' : "") +
    (meta.type === "number" ? ' step="' + (meta.kind === "integer" ? "1" : "any") + '" min="' + (meta.minimum ?? 0.000001) + '" inputmode="decimal"' : "") + ' />';
  return '<div class="field ' + (options.wide || meta.multiline || /_URL$/.test(name) || meta.secret ? "wide" : "") + '">' +
    '<label for="' + id + '">' + escapeHtml(label) + (required ? '<b>*</b>' : "") + '</label>' +
    (meta.secret ? '<div class="secret-control">' + input + revealButton(id, label) + '</div>' : input) +
    '<small id="hint-' + name + '">' + escapeHtml(meta.secret ? t(value ? "ui.draftSecret" : configured ? "ui.configuredSecret" : "notConfigured") : (llmText(meta.help_zh, meta.help_en) || (meta.kind === "list" ? llmText("每行一个值。", "One value per line.") : "")) + (meta.choices ? llmText(" 可选值：", " Allowed values: ") + meta.choices.join(", ") : "")) + '</small>' +
    (error ? '<small id="error-' + name + '" class="field-error">' + t(error.message) + '</small>' : "") + '</div>';
}
function revealButton(id, label) {
  return '<button type="button" class="quiet secret-toggle" data-reveal="' + escapeAttr(id) + '" aria-label="' + escapeAttr(t("ui.show") + " " + label) + '" aria-pressed="false">' + t("ui.show") + '</button>';
}
function normalizeAgents(agents) {
  return agents.map((agent) => ({
    name: agent.name, enabled: agent.enabled !== false, has_config: !!agent.has_config,
    caller: { role: agent.caller?.role || "role_play", shared_artifact_read: !!agent.caller?.shared_artifact_read, gateway_token_configured: !!agent.caller?.gateway_token_configured, gateway_token: "" },
    matrix: { enabled: agent.matrix?.enabled !== false, account: agent.matrix?.account ?? agent.name, homeserver: agent.matrix?.homeserver || "", access_token_configured: !!agent.matrix?.access_token_configured, access_token: "" },
    high_risk_tools: [...(agent.high_risk_tools || [])].sort()
  }));
}
function renderMatrix() {
  const active = draftAgents.find((agent) => agent.name === activeAgent) || draftAgents[0];
  activeAgent = active?.name || null;
  return '<div class="config-layout"><div class="config-stack"><section class="panel">' +
    panelHeading("Matrix", t("ui.connectionDesc"), moduleStatus("matrix")) + '<div class="form-grid">' + field("MATRIX_HOMESERVER") +
    '</div></section><section class="panel">' +
    panelHeading("Agent", t("ui.matrixDesc"), '<button type="button" class="secondary small" data-add-agent>' + icon("plus") + t("ui.addAgent") + '</button>') +
    (draftAgents.length ? '<div class="agent-bar" role="group" aria-label="Agent">' + draftAgents.map((agent) => '<button type="button" class="agent-tab ' +
      (agent.name === activeAgent ? "active" : "") + '" aria-pressed="' + (agent.name === activeAgent) + '" data-agent="' + escapeAttr(agent.name) + '"><span class="status-dot ' +
      (agent.enabled ? "ok" : "") + '"></span>' + escapeHtml(agent.name) + '</button>').join("") + '</div>' : "") +
    (active ? agentPanel(active) : '<div class="empty-state">' + icon("matrix") + '<h3>' + t("noAgentTitle") + '</h3><p>' + t("ui.noAgentBody") +
      '</p><button type="button" data-add-agent>' + icon("plus") + t("ui.addAgent") + '</button></div>') +
    '</section>' + advancedPanel(["MATRIX_TIMEOUT_SECONDS", "MATRIX_MAX_TEXT_CHARS"]) + '</div>' + guide() + '</div>';
}
function agentPanel(agent) {
  const check = (path, label, value) => '<label class="inline-check"><input id="agent-' + path.replaceAll(".", "-") + '" type="checkbox" data-agent-field="' + path + '"' + (value ? " checked" : "") + ' /><span>' + label + '</span></label>';
  return '<div class="agent-panel"><div class="agent-panel-head"><div><h3>' + escapeHtml(agent.name) + '</h3><p>' + t(agent.has_config ? "existingConfig" : "newConfig") +
    '</p></div><button type="button" class="quiet danger small" data-remove-agent>' + t("remove") + '</button></div><div class="form-grid">' +
    '<div class="field wide">' + check("enabled", t("agentEnabled"), agent.enabled) + '</div>' +
    '<label class="field wide"><span>' + llmText("调用者角色", "Caller role") + '</span><select data-agent-field="caller.role"><option value="role_play"' + (agent.caller.role === "role_play" ? " selected" : "") + '>role_play</option><option value="admin"' + (agent.caller.role === "admin" ? " selected" : "") + '>admin</option></select></label>' +
    agentField(agent, "Gateway Token", "caller.gateway_token", true, agent.caller.gateway_token_configured) +
    '<div class="field wide">' + check("matrix.enabled", llmText("使用 Matrix 发送账号", "Use Matrix sender account"), agent.matrix.enabled) + '</div>' +
    agentField(agent, "Matrix Access Token", "matrix.access_token", true, agent.matrix.access_token_configured) +
    agentField(agent, "Matrix Account", "matrix.account", false, false) +
    agentField(agent, llmText("账号专用 Homeserver（可选）", "Account homeserver (optional)"), "matrix.homeserver", false, false) +
    '<div class="field wide">' + check("caller.shared_artifact_read", t("sharedArtifactRead"), agent.caller.shared_artifact_read) + '</div></div>' +
    '<div class="tool-checks"><strong>' + t("ui.permissions") + '</strong>' +
    ["matrix_send_text", "matrix_send_image", "matrix_send_audio", "printer_print_file"].map((tool) => '<label><input type="checkbox" data-tool="' + tool + '"' + (agent.high_risk_tools.includes(tool) ? " checked" : "") + ' /><span>' + tool + '</span></label>').join("") + '</div></div>';
}
function agentField(agent, label, path, secret, configured) {
  const required = path !== "matrix.homeserver" && (path.startsWith("caller.") || agent.matrix.enabled);
  const value = path.split(".").reduce((target, key) => target[key], agent) || "";
  const id = "agent-" + path.replaceAll(".", "-"), error = errors.find((item) => item.agent === agent.name && item.field === path);
  return '<div class="field wide"><label for="' + id + '">' + label + (required ? '<b>*</b>' : '') + '</label><div class="' + (secret ? "secret-control" : "") + '">' +
    '<input id="' + id + '" data-agent-field="' + path + '" aria-label="' + label + '" type="' + (secret ? "password" : "text") + '" value="' + escapeAttr(value) +
    '" placeholder="' + (configured ? t("configuredReplace") : "") + '"' + (secret ? ' data-secret="true" autocomplete="new-password"' : "") +
    (agent.enabled && required && !configured ? " required" : "") + (error ? ' class="invalid" aria-invalid="true" aria-describedby="' + id + '-error"' : "") + ' />' +
    (secret ? revealButton(id, label) : "") + '</div>' + (secret ? '<small>' + t(value ? "ui.draftSecret" : configured ? "ui.configuredSecret" : "notConfigured") + '</small>' : "") +
    (error ? '<small id="' + id + '-error" class="field-error">' + t(error.message) + '</small>' : "") + '</div>';
}
function validationSummary() {
  if (!errors.length) return "";
  return '<section class="validation-summary" role="alert"><h3>' + t("ui.validation", { count: errors.length }) + '</h3><p>' + t("ui.validationHint") + '</p>' +
    errors.map((error, index) => '<button type="button" data-error-index="' + index + '">' +
      escapeHtml(error.agent ? t("ui.agentError", { name: error.agent, field: error.field }) : t("modules." + error.module + ".label") + " · " + fieldLabel(error.field)) +
      ' — ' + t(error.message) + ' ↗</button>').join("") + '</section>';
}
function handleInput(event) {
  const input = event.target;
  if (busy || input.type === "checkbox") return;
  if (input.name && (FIELD_META[input.name] || lastStatus?.settings_schema?.[input.name])) {
    updateLocalField(input.name, input.value.trim());
    if (input.name === "LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH") workflowSelection = null;
  } else if (input.dataset.agentField) {
    const agent = draftAgents.find((item) => item.name === activeAgent);
    if (agent) setDeep(agent, input.dataset.agentField, input.value.trim());
    savedNotice = false;
  } else return;
  errors = errors.filter((error) => input.name ? error.agent || error.field !== input.name : error.agent !== activeAgent || error.field !== input.dataset.agentField);
  input.classList.remove("invalid"); input.removeAttribute("aria-invalid");
  input.closest(".field")?.querySelector(".field-error")?.remove();
  if (input.dataset.secret) {
    const hint = input.closest(".field")?.querySelector("small");
    const agent = draftAgents.find((item) => item.name === activeAgent);
    const configured = input.name ? !!({ ...lastStatus.local_env, ...lastStatus.webui?.owned_fields })[input.name] :
      input.dataset.agentField === "caller.gateway_token" ? agent?.caller.gateway_token_configured : agent?.matrix.access_token_configured;
    if (hint) hint.textContent = t(input.value.trim() ? "ui.draftSecret" : configured ? "ui.configuredSecret" : "notConfigured");
  }
  const summary = $(".validation-summary");
  if (summary) summary.outerHTML = validationSummary();
  renderNav(); updateDraftBar();
}
function handleChange(event) {
  const input = event.target;
  if (busy) return;
  if (input.tagName === "SELECT") { handleInput(event); return; }
  if (input.type !== "checkbox" || input.hasAttribute("data-model-add") || input.hasAttribute("data-model-tag")) return;
  if (Object.values(MODULE_SWITCHES).includes(input.name) || lastStatus?.settings_schema?.[input.name]?.type === "boolean") {
    updateLocalField(input.name, String(input.checked));
  } else {
    const agent = draftAgents.find((item) => item.name === activeAgent);
    if (!agent) return;
    if (input.dataset.agentField) setDeep(agent, input.dataset.agentField, input.checked);
    else if (input.dataset.tool) {
      const selected = new Set(agent.high_risk_tools);
      input.checked ? selected.add(input.dataset.tool) : selected.delete(input.dataset.tool);
      agent.high_risk_tools = [...selected].sort();
    }
    savedNotice = false;
  }
  errors = [];
  renderAll();
}
async function handlePageClick(event) {
  const button = event.target.closest("button");
  if (!button || busy) return;
  if (button.hasAttribute("data-workflow")) {
    const id = button.dataset.workflow;
    if (id === inferWorkflow()) return;
    if (id !== "custom" && getValue("LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH") &&
      !await openDialog({ title: t("ui.workflowTitle"), description: t("ui.workflowConfirm") })) return;
    applyWorkflow(id); renderAll();
  } else if (button.hasAttribute("data-agent")) {
    activeAgent = button.dataset.agent; renderAll();
  } else if (button.hasAttribute("data-add-agent")) await addAgent();
  else if (button.hasAttribute("data-remove-agent")) await removeActiveAgent();
  else if (button.hasAttribute("data-error-index")) focusError(errors[Number(button.dataset.errorIndex)]);
}
function setDeep(target, path, value) {
  const keys = path.split(".");
  let current = target;
  keys.slice(0, -1).forEach((key) => { current = current[key] ||= {}; });
  current[keys.at(-1)] = value;
}
function applyWorkflow(id) {
  workflowSelection = id;
  if (id === "custom") return;
  updateLocalField("LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH", WORKFLOWS[id].path);
  Object.entries(WORKFLOWS[id].defaults).forEach(([key, value]) => updateLocalField(key, value));
  errors = [];
}
async function addAgent() {
  const name = await openDialog({
    title: t("ui.addAgent"), description: t("ui.newAgentDesc"), confirm: t("ui.addAgent"), input: true,
    validate: (value) => !/^[A-Za-z0-9_-]+$/.test(value) ? t("agentNameInvalid") : draftAgents.some((agent) => agent.name === value) ? t("ui.agentDuplicate") : ""
  });
  if (!name) return;
  draftAgents.push(normalizeAgents([{ name, enabled: false, high_risk_tools: ["matrix_send_text", "matrix_send_image", "matrix_send_audio"] }])[0]);
  activeAgent = name; savedNotice = false; renderAll();
  document.getElementById("agent-caller-gateway_token")?.focus();
}
async function removeActiveAgent() {
  if (!activeAgent || !await openDialog({ title: t("ui.removeAgent", { name: activeAgent }), description: t("ui.removeAgentDesc"), confirm: t("remove") })) return;
  draftAgents = draftAgents.filter((agent) => agent.name !== activeAgent);
  activeAgent = draftAgents[0]?.name || null; errors = []; savedNotice = false; renderAll();
}
function requiredMissing(id, values = getValues()) {
  const fields = [...(MODULE_REQUIRED_FIELDS[id] || [])];
  if (id === "localimage" && inferWorkflow() !== "custom") fields.push(...WORKFLOWS[inferWorkflow()].fields);
  return fields.filter((name) => !String(values[name] ?? "").trim());
}
function agentMissing(agent) {
  const missing = [];
  if (!agent.caller.gateway_token_configured && !agent.caller.gateway_token.trim()) missing.push("caller.gateway_token");
  if (agent.matrix.enabled && !agent.matrix.access_token_configured && !agent.matrix.access_token.trim()) missing.push("matrix.access_token");
  if (agent.matrix.enabled && !agent.matrix.account.trim()) missing.push("matrix.account");
  return missing;
}
function validateDraft() {
  const result = [], values = getValues();
  Object.keys(MODULE_SWITCHES).filter(moduleEnabled).forEach((module) => {
    requiredMissing(module, values).forEach((field) => result.push({ module, field, message: "ui.missingField" }));
  });
  if (getValue("IMAGE_MODEL_ID") && (moduleEnabled("image") || "IMAGE_MODEL_ID" in draftFields) && !imageModels().some((model) => model.id === getValue("IMAGE_MODEL_ID"))) {
    result.push({ module: "image", field: "IMAGE_MODEL_ID", message: "ui.missingModel" });
  }
  if (moduleEnabled("matrix") && !getValue("MATRIX_ACCESS_TOKEN") && !draftAgents.some((agent) => agent.enabled && agent.matrix.enabled && (agent.matrix.access_token_configured || agent.matrix.access_token))) {
    result.push({ module: "matrix", field: "MATRIX_ACCESS_TOKEN", message: "ui.missingField" });
  }
  new Set([...Object.keys(FIELD_META), ...Object.keys(lastStatus.settings_schema || {})]).forEach((field) => {
    const meta = metadata(field);
    const value = String(values[field] ?? "").trim(), module = fieldModule(field);
    if (!moduleEnabled(module) && !(field in draftFields)) return;
    if (result.some((error) => error.field === field)) return;
    let message = "";
    if (meta.type === "number" && (value || field in draftFields)) {
      if (!value || !Number.isFinite(Number(value)) || Number(value) < (meta.minimum ?? 0.000001)) message = meta.minimum === 0 ? "ui.nonnegative" : "ui.invalidNumber";
      else if ((meta.kind === "integer" || /(BYTES|CHARS|COPIES)$/.test(field)) && !Number.isInteger(Number(value))) message = "ui.invalidInteger";
    }
    if (meta.kind === "json") { try { const parsed = JSON.parse(value); if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") message = "ui.invalidJson"; } catch { message = "ui.invalidJson"; } }
    if (meta.kind === "list") {
      const items = value.split(/[\n,;]/).map((item) => item.trim()).filter(Boolean);
      if (!items.length && !meta.allow_empty) message = "ui.missingField";
      if (meta.choices && items.some((item) => !meta.choices.includes(item))) message = "ui.invalidChoice";
    }
    if (/_URL$/.test(field) && value) {
      try { const url = new URL(value); if (!["http:", "https:"].includes(url.protocol)) message = "ui.invalidUrl"; }
      catch { message = "ui.invalidUrl"; }
    }
    if (message) result.push({ module, field, message });
  });
  if (agentsChanged()) draftAgents.filter((agent) => agent.enabled).forEach((agent) => {
    agentMissing(agent).forEach((field) => result.push({ module: "matrix", agent: agent.name, field, message: "ui.missingField" }));
  });
  return result;
}
function focusError(error) {
  if (!error) return;
  currentPage = error.module;
  if (error.agent) activeAgent = error.agent;
  history.replaceState(null, "", "#" + currentPage);
  renderAll();
  const input = error.agent ? document.getElementById("agent-" + error.field.replaceAll(".", "-")) : document.getElementById("field-" + error.field);
  input?.closest("details")?.setAttribute("open", "");
  input?.focus(); input?.scrollIntoView({ block: "center", behavior: "auto" });
}
function commitSavedDraft() {
  // A confirmed POST must not be submitted again if the subsequent GET fails.
  const committed = { ...draftFields };
  Object.keys(committed).forEach((name) => { if (metadata(name).secret && committed[name]) committed[name] = "********"; });
  lastStatus.local_env = { ...lastStatus.local_env, ...lastStatus.webui?.owned_fields, ...committed };
  lastStatus.webui.owned_fields = {};
  draftAgents.forEach((agent) => {
    if (agent.caller.gateway_token) agent.caller.gateway_token_configured = true;
    if (agent.matrix.access_token) agent.matrix.access_token_configured = true;
    agent.caller.gateway_token = ""; agent.matrix.access_token = ""; agent.has_config = true;
  });
  baselineAgents = clone(draftAgents); draftFields = {}; errors = []; savedNotice = true;
}
async function saveConfig(event) {
  event?.preventDefault();
  if (busy || !lastStatus || !changeCount() || currentPage === "llm") return;
  errors = validateDraft();
  if (errors.length) { focusError(errors[0]); return; }
  const body = { owned_fields: { ...draftFields } };
  if (agentsChanged()) body.agents = clone(draftAgents);
  busy = "save"; updateChrome();
  try {
    await request("/admin/api/config", body);
    commitSavedDraft();
    try {
      acceptStatus(await request("/admin/api/status"), true);
      savedNotice = true;
      showMessage(t(lastStatus.restart_required ? "ui.needsRestart" : "ui.applied"), "success");
    } catch { showMessage(t("ui.savedRefreshFailed"), "warning"); }
  } catch (error) { showMessage(t("ui.saveFailed", { message: error.message }), "danger"); }
  finally { busy = ""; renderAll(); }
}



Object.assign(STRINGS["zh-CN"].ui, {
  tokenHint: "登录密钥只在当前标签页会话中保留。", tokenRequired: "请输入登录密钥。",
  sessionExpired: "登录已失效，请退出后使用新的登录密钥连接。", disconnectedMessage: "已退出登录，并清除本次会话的密钥。",
  disconnect: "退出登录", saveHint: "草稿在页面间保留 · 普通配置立即生效，模块开关需重启",
  guideDesc: "填写连接信息，启用模块并保存。只有模块开关变化需要重启网关。",
  configuredHint: "模块开关在重启后生效", stepThree: "若更改模块开关，重启网关",
  needsRestart: "配置已保存。模块开关变化需要重启服务。", applied: "配置已保存并立即生效。",
  configPath: "配置数据库", imageDesc: "选择已添加的图片模型，生成与编辑图片。",
  settingsDesc: "管理调用额度、文件存储与 MCP 访问权限。", llmDesc: "连接模型服务商，集中管理可用模型与能力标签。",
  removeAgentDesc: "保存后，将从配置数据库中移除此 Agent。", refreshDesc: "未保存的配置、服务商和模型草稿都会被服务器内容替换。",
  invalidJson: "请输入有效的 JSON 对象", invalidChoice: "列表中存在不支持的值，请查看字段说明", nonnegative: "请输入大于或等于 0 的数字",
  quotas: "调用额度与并发", quotasDesc: "设置使用额度、计数周期与并发上限。0 表示不限制。",
  storage: "文件与审计", storageDesc: "管理文件访问链接、大小和有效期。", policy: "权限与调用者", policyDesc: "MCP 调用密钥独立于 WebUI 登录密钥。",
  parameters: "参数与限制", parametersDesc: "列表每行一项。保存后工具参数同步更新。",
  selectModel: "请选择图片模型", missingModel: "当前模型不可用，请重新选择", modelLink: "在 LLM 管理中添加并标记 image 模型",
  providerName: "服务商名称", providers: "模型服务商", providerDesc: "连接兼容 OpenAI 的服务，统一管理模型。",
  newProvider: "新增服务商", saveProvider: "保存服务商", fetchModels: "保存并获取模型", providerSelect: "选择服务商",
  llmNotice: "服务商和模型使用各自的保存按钮，保存后立即生效。配置页的草稿会保留。",
  providerRequired: "请填写名称、有效的 HTTP(S) 地址和 API Key。", providerSaved: "服务商已保存。",
  models: "模型列表", modelsDesc: "勾选可用模型并设置能力。标记 image 的模型可用于远程生图。",
  modelSearch: "搜索模型", manualModel: "手动输入模型 ID", addModel: "添加", saveModels: "保存模型选择",
  emptyModels: "还没有模型。获取服务商模型列表，或手动添加模型 ID。", modelTagsRequired: "每个选中的模型至少需要一个能力标签。",
  modelsSaved: "模型选择与标签已保存。", modelsFetched: "已获取模型列表，请选择需要的模型并保存。",
  deleteProvider: "删除此服务商？", deleteProviderDesc: "此操作立即删除服务商及其模型。正在使用的图片模型需先在配置页更换。",
  llmDirty: "此页有未保存更改", llmClean: "服务商与模型配置已同步", discardLLM: "放弃模型管理草稿",
  llmDiscardDesc: "服务商输入、模型选择与标签将恢复到已保存的内容。", noResults: "没有匹配的模型",
  discoverFailed: "服务商已保存，但获取模型失败：{message}", llmProviderRemoved: "服务商已删除。"
});
Object.assign(STRINGS.en.ui, {
  tokenHint: "The login key is kept only in this tab's session.", tokenRequired: "Enter your login key.",
  sessionExpired: "Your login has expired. Log out and connect with your new login key.", disconnectedMessage: "Logged out. The session key has been cleared.",
  disconnect: "Log out", saveHint: "Drafts stay across pages · Settings apply immediately; module switches need restart",
  guideDesc: "Add a connection, enable the module, and save. Only module switch changes require a restart.",
  configuredHint: "Module switches apply after restart", stepThree: "Restart if you changed a module switch",
  needsRestart: "Configuration saved. Restart the service to apply module switch changes.", applied: "Configuration saved and applied immediately.",
  configPath: "Config database", imageDesc: "Select an added image model to generate and edit images.",
  settingsDesc: "Manage usage quotas, artifacts, and MCP access permissions.", llmDesc: "Connect providers and manage available models and capability tags.",
  removeAgentDesc: "After saving, this agent will be removed from the configuration database.", refreshDesc: "Unsaved configuration, provider, and model drafts will be replaced with server data.",
  invalidJson: "Enter a valid JSON object", invalidChoice: "The list contains unsupported values; check the field help", nonnegative: "Enter a number greater than or equal to 0",
  quotas: "Quotas & concurrency", quotasDesc: "Manage usage windows and concurrent jobs. 0 means unlimited.",
  storage: "Artifacts & audit", storageDesc: "Manage download links, size limits, and expiry.", policy: "Permissions & callers", policyDesc: "MCP credentials are separate from the WebUI login key.",
  parameters: "Parameters & limits", parametersDesc: "One value per line in lists. Tool parameters update on save.",
  selectModel: "Select an image model", missingModel: "Current model unavailable; select another", modelLink: "Add and tag image models in LLM Management",
  providerName: "Provider name", providers: "Model providers", providerDesc: "Connect an OpenAI-compatible service and manage its models.",
  newProvider: "New provider", saveProvider: "Save provider", fetchModels: "Save & fetch models", providerSelect: "Select provider",
  llmNotice: "Save providers and models using their own buttons. Changes apply immediately. Configuration drafts are kept.",
  providerRequired: "Enter a name, a valid HTTP(S) URL, and an API key.", providerSaved: "Provider saved.",
  models: "Model catalog", modelsDesc: "Select models and set capabilities. Models tagged image are available for remote image generation.",
  modelSearch: "Search models", manualModel: "Enter a model ID manually", addModel: "Add", saveModels: "Save model selection",
  emptyModels: "No models yet. Fetch models from the provider or add a model ID manually.", modelTagsRequired: "Each selected model needs at least one capability tag.",
  modelsSaved: "Model selection and tags saved.", modelsFetched: "Models fetched. Select the models you need and save.",
  deleteProvider: "Delete this provider?", deleteProviderDesc: "This immediately deletes the provider and its models. Change any selected image model in configuration first.",
  llmDirty: "This page has unsaved changes", llmClean: "Providers and models are up to date", discardLLM: "Discard catalog drafts",
  llmDiscardDesc: "Provider inputs, model selections, and tags will return to their saved values.", noResults: "No matching models",
  discoverFailed: "Provider saved, but model discovery failed: {message}", llmProviderRemoved: "Provider deleted."
});
ICONS.llm = '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/><rect x="9" y="9" width="6" height="6" rx="1"/>';
function settingsGroup(group, title, description, collapsed = false) {
  const fields = Object.entries(lastStatus.settings_schema || {}).filter(([name, spec]) => spec.group === group && name !== "LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS");
  if (!fields.length) return "";
  const open = errors.some((error) => fields.some(([name]) => name === error.field));
  const content = '<div class="form-grid">' + fields.map(([name]) => field(name)).join("") + '</div>';
  return collapsed
    ? '<details class="panel advanced operational-panel"' + (open ? " open" : "") + '><summary>' + icon("settings") + title + '</summary>' + content + '</details>'
    : '<section class="panel">' + panelHeading(title, description) + content + '</section>';
}
function renderSettings() {
  return '<div class="config-layout"><div class="config-stack">' +
    settingsGroup("quotas", t("ui.quotas"), t("ui.quotasDesc")) +
    settingsGroup("storage", t("ui.storage"), t("ui.storageDesc"), true) +
    settingsGroup("policy", t("ui.policy"), t("ui.policyDesc"), true) + '</div>' + guide() + '</div>';
}
function imageModels() {
  return (lastStatus.llm?.providers || []).flatMap((provider) => provider.models.filter((model) => model.tags.includes("image")).map((model) => ({ ...model, providerName: provider.name })));
}
function imageModelField() {
  const selected = getValue("IMAGE_MODEL_ID"), models = imageModels();
  const error = errors.find((item) => item.field === "IMAGE_MODEL_ID");
  return '<div class="field wide"><label for="field-IMAGE_MODEL_ID">' + t("field.model") + '<b>*</b></label>' +
    '<select id="field-IMAGE_MODEL_ID" name="IMAGE_MODEL_ID"' + (moduleEnabled("image") ? " required" : "") + (error ? ' class="invalid" aria-invalid="true"' : "") + '><option value="">' + t("ui.selectModel") + '</option>' +
    (selected && !models.some((model) => model.id === selected) ? '<option value="' + escapeAttr(selected) + '" selected>' + t("ui.missingModel") + '</option>' : "") +
    models.map((model) => '<option value="' + escapeAttr(model.id) + '"' + (selected === model.id ? " selected" : "") + '>' + escapeHtml(model.providerName + " / " + model.model_id) + '</option>').join("") +
    '</select><small><a href="#llm">' + t("ui.modelLink") + '</a></small>' + (error ? '<small class="field-error">' + t(error.message) + '</small>' : "") + '</div>';
}
function providerBase(id) {
  const provider = lastStatus?.llm?.providers?.find((item) => item.id === id);
  return { name: provider?.name || "", base_url: provider?.base_url || "", api_key: "" };
}
function providerDraft(id) { return providerDrafts[id] ||= providerBase(id); }
function modelsFor(id) {
  return modelDrafts[id] ||= (lastStatus.llm?.providers?.find((item) => item.id === id)?.models || []).map((model) => ({ ...model, tags: [...model.tags], added: true }));
}
function selectedModels(rows) {
  return rows.filter((model) => model.added).map(({ model_id, tags }) => ({ model_id, tags: [...tags].sort() })).sort((a, b) => a.model_id.localeCompare(b.model_id));
}
function llmChangeCount() {
  let count = Object.keys(providerDrafts).filter((id) => JSON.stringify(providerDrafts[id]) !== JSON.stringify(providerBase(id))).length;
  Object.entries(modelDrafts).forEach(([id, rows]) => {
    const baseline = (lastStatus?.llm?.providers?.find((item) => item.id === id)?.models || []).map((model) => ({ ...model, added: true }));
    if (JSON.stringify(selectedModels(rows)) !== JSON.stringify(selectedModels(baseline))) count++;
  });
  return count;
}
function renderLLM() {
  const providers = lastStatus.llm?.providers || [];
  if (activeProvider === null) activeProvider = providers[0]?.id || "";
  const provider = providers.find((item) => item.id === activeProvider);
  const draft = providerDraft(activeProvider), rows = provider ? modelsFor(activeProvider) : [];
  return '<div class="catalog-notice"><p>' + t("ui.llmNotice") + '</p><span id="llmDraftInfo">' + t(llmChangeCount() ? "ui.llmDirty" : "ui.llmClean") + '</span></div>' +
    '<div class="config-stack"><section class="panel">' + panelHeading(t("ui.providers"), t("ui.providerDesc"), '<button type="button" id="newProvider" class="secondary small">' + icon("plus") + t("ui.newProvider") + '</button>') +
    '<div class="form-grid"><label class="field wide"><span>' + t("ui.providerSelect") + '</span><select id="providerSelect"><option value="">' + t("ui.newProvider") + '</option>' + providers.map((item) => '<option value="' + escapeAttr(item.id) + '"' + (activeProvider === item.id ? " selected" : "") + '>' + escapeHtml(item.name) + '</option>').join("") + '</select></label>' +
    '<label class="field"><span>' + t("ui.providerName") + '<b>*</b></span><input id="providerName" data-provider-field="name" value="' + escapeAttr(draft.name) + '" /></label>' +
    '<label class="field"><span>API Base URL <b>*</b></span><input id="providerUrl" data-provider-field="base_url" value="' + escapeAttr(draft.base_url) + '" placeholder="https://api.example.com/v1" /></label>' +
    '<div class="field wide"><label for="providerKey">API Key <b>*</b></label><div class="secret-control"><input id="providerKey" aria-label="API Key" type="password" autocomplete="new-password" data-provider-field="api_key" value="' + escapeAttr(draft.api_key) + '" placeholder="' + (provider?.key_configured ? t("configuredReplace") : "sk-…") + '" />' + revealButton("providerKey", "API Key") + '</div></div></div>' +
    '<div class="panel-actions"><button type="button" id="saveProvider">' + t("ui.saveProvider") + '</button><button type="button" id="fetchModels" class="secondary">' + t("ui.fetchModels") + '</button>' +
    (provider ? '<button type="button" id="deleteProvider" class="quiet danger">' + t("remove") + '</button>' : "") + '</div></section>' +
    (provider ? '<section class="panel">' + panelHeading(t("ui.models") + ' <span class="status-pill">' + rows.length + '</span>', t("ui.modelsDesc")) +
    '<div class="model-toolbar"><input id="modelSearch" placeholder="' + t("ui.modelSearch") + '" aria-label="' + t("ui.modelSearch") + '" value="' + escapeAttr(modelSearch) + '" />' +
    '<div class="manual-model"><input id="manualModel" placeholder="' + t("ui.manualModel") + '" aria-label="' + t("ui.manualModel") + '" /><button type="button" id="addManualModel" class="secondary">' + t("ui.addModel") + '</button></div></div>' +
    '<div class="model-list">' + rows.map((model, index) => '<div class="model-row" data-model-index="' + index + '"' + (!model.model_id.toLowerCase().includes(modelSearch.toLowerCase()) ? ' hidden' : '') + '><label><input type="checkbox" data-model-add="' + index + '"' + (model.added ? " checked" : "") + ' /><span>' + escapeHtml(model.model_id) + '</span></label><div class="model-tags">' +
    ["text", "image"].map((tag) => '<label><input type="checkbox" data-model-tag="' + tag + '" data-model="' + index + '"' + (model.tags.includes(tag) ? " checked" : "") + ' /><span>' + tag + '</span></label>').join("") + '</div></div>').join("") +
    '<p id="noModels" class="model-empty"' + (rows.some((model) => model.model_id.toLowerCase().includes(modelSearch.toLowerCase())) ? " hidden" : "") + '>' + t(rows.length ? "ui.noResults" : "ui.emptyModels") + '</p></div>' +
    '<div class="panel-actions"><button type="button" id="saveModels">' + t("ui.saveModels") + '</button></div></section>' : "") +
    '<div class="catalog-footer"><button id="discardLLM" type="button" class="quiet">' + t("ui.discardLLM") + '</button></div></div>';
}
async function llmAction(action) {
  if (busy) return;
  busy = "llm"; updateChrome();
  try { await action(); }
  catch (error) { showMessage(error.message, "danger"); }
  finally { busy = ""; renderAll(); }
}
async function llmRequest(path, body) {
  const payload = await request("/admin/api/llm/" + path, body);
  if (payload.providers) lastStatus.llm = { providers: payload.providers };
  return payload;
}
async function saveProviderDraft() {
  const id = activeProvider, draft = { ...providerDraft(id) };
  const provider = lastStatus.llm?.providers.find((item) => item.id === id);
  let validUrl = false;
  try { const url = new URL(draft.base_url); validUrl = ["https:", "http:"].includes(url.protocol) && !url.username && !url.password && !url.search && !url.hash; } catch { /* Field error below. */ }
  if (!draft.name.trim() || !validUrl || (!draft.api_key.trim() && !provider?.key_configured)) throw new Error(t("ui.providerRequired"));
  const payload = await llmRequest("providers/save", { ...(id ? { id } : {}), ...draft });
  delete providerDrafts[id];
  activeProvider = payload.provider_id;
  return activeProvider;
}
function attachLLMHandlers() {
  $("#newProvider").addEventListener("click", () => { activeProvider = ""; modelSearch = ""; renderAll(); });
  $("#providerSelect").addEventListener("change", (event) => { activeProvider = event.target.value; modelSearch = ""; renderAll(); });
  document.querySelectorAll("[data-provider-field]").forEach((input) => input.addEventListener("input", () => {
    providerDraft(activeProvider)[input.dataset.providerField] = input.value.trim();
    $("#llmDraftInfo").textContent = t(llmChangeCount() ? "ui.llmDirty" : "ui.llmClean"); renderNav();
  }));
  $("#saveProvider").addEventListener("click", () => llmAction(async () => { await saveProviderDraft(); showMessage(t("ui.providerSaved"), "success"); }));
  $("#fetchModels").addEventListener("click", () => llmAction(async () => {
    const id = await saveProviderDraft();
    try {
      const payload = await llmRequest("discover", { provider_id: id });
      const known = new Map(modelsFor(id).map((model) => [model.model_id, model]));
      payload.models.forEach((model_id) => { if (!known.has(model_id)) known.set(model_id, { model_id, added: false, tags: ["text"] }); });
      modelDrafts[id] = [...known.values()].sort((a, b) => a.model_id.localeCompare(b.model_id));
      showMessage(t("ui.modelsFetched"), "success");
    } catch (error) { showMessage(t("ui.discoverFailed", { message: error.message }), "warning"); }
  }));
  $("#deleteProvider")?.addEventListener("click", async () => {
    if (!await openDialog({ title: t("ui.deleteProvider"), description: t("ui.deleteProviderDesc"), confirm: t("remove") })) return;
    llmAction(async () => {
      const id = activeProvider; await llmRequest("providers/delete", { provider_id: id });
      delete providerDrafts[id]; delete modelDrafts[id]; activeProvider = null;
      showMessage(t("ui.llmProviderRemoved"), "success");
    });
  });
  const addManual = () => {
    const model_id = $("#manualModel").value.trim();
    if (!model_id) return;
    const rows = modelsFor(activeProvider), existing = rows.find((model) => model.model_id === model_id);
    if (existing) existing.added = true; else rows.push({ model_id, added: true, tags: ["text"] });
    modelSearch = ""; renderAll(); $("#manualModel")?.focus();
  };
  $("#addManualModel")?.addEventListener("click", addManual);
  $("#manualModel")?.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); addManual(); } });
  document.querySelectorAll("[data-model-add], [data-model-tag]").forEach((input) => input.addEventListener("change", () => {
    const model = modelsFor(activeProvider)[Number(input.dataset.modelAdd ?? input.dataset.model)];
    if (input.hasAttribute("data-model-add")) model.added = input.checked;
    else model.tags = input.checked ? [...new Set([...model.tags, input.dataset.modelTag])] : model.tags.filter((tag) => tag !== input.dataset.modelTag);
    $("#llmDraftInfo").textContent = t(llmChangeCount() ? "ui.llmDirty" : "ui.llmClean"); renderNav();
  }));
  $("#saveModels")?.addEventListener("click", () => llmAction(async () => {
    const id = activeProvider, models = selectedModels(modelsFor(id));
    if (models.some((model) => !model.tags.length)) throw new Error(t("ui.modelTagsRequired"));
    await llmRequest("models/save", { provider_id: id, models });
    delete modelDrafts[id]; showMessage(t("ui.modelsSaved"), "success");
  }));
  $("#modelSearch")?.addEventListener("input", (event) => {
    modelSearch = event.target.value;
    document.querySelectorAll("[data-model-index]").forEach((row) => { row.hidden = !modelsFor(activeProvider)[Number(row.dataset.modelIndex)].model_id.toLowerCase().includes(modelSearch.toLowerCase()); });
    $("#noModels").hidden = !!document.querySelector("[data-model-index]:not([hidden])");
    $("#noModels").textContent = t("ui.noResults");
  });
  $("#discardLLM").addEventListener("click", async () => {
    if (!llmChangeCount()) return;
    if (!await openDialog({ title: t("ui.discardLLM"), description: t("ui.llmDiscardDesc"), confirm: t("ui.discard") })) return;
    providerDrafts = {}; modelDrafts = {}; renderAll();
  });
}
init();
