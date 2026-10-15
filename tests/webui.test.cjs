const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM, VirtualConsole } = require("jsdom");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "webui/index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "webui/app.js"), "utf8");
const copy = (value) => JSON.parse(JSON.stringify(value));
const tick = () => new Promise((resolve) => setImmediate(resolve));
function fixture() {
  return {
    ok: true, dev_mode: false, restart_required: false,
    server: { name: "home_mcp_gateway", version: "0.2.2", host: "127.0.0.1", port: 8787 },
    webui: { enabled: true, storage: "sqlite", active_snapshot: "./test.sqlite3", owned_fields: {} },
    modules: Object.fromEntries(["image", "localimage", "tts", "matrix", "printer"].map((id) => [id, { enabled: false }])),
    local_env: {
      IMAGE_MODULE_ENABLED: "false", LOCAL_IMAGE_MODULE_ENABLED: "false", TTS_MODULE_ENABLED: "false", MATRIX_MODULE_ENABLED: "false", PRINTER_MODULE_ENABLED: "false",
      IMAGE_MODEL_ID: "image-model-1", IMAGE_TOTAL_TIMEOUT_SECONDS: "300", IMAGE_PROVIDER_TIMEOUT_SECONDS: "120", IMAGE_MAX_DOWNLOAD_BYTES: "1000000",
      LOCAL_IMAGE_COMFYUI_BASE_URL: "http://localhost:8188", LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS: "localhost\n127.0.0.1",
      LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH: "./custom.json", LOCAL_IMAGE_DEFAULT_SIZE: "1024x1024", LOCAL_IMAGE_DEFAULT_QUALITY: "standard",
      LOCAL_IMAGE_DEFAULT_STYLE: "default", LOCAL_IMAGE_DEFAULT_OUTPUT_FORMAT: "png", LOCAL_IMAGE_COMFYUI_CHECKPOINT: "custom.safetensors",
      TTS_LOCAL_HTTP_URL: "http://localhost:9000/tts", TTS_API_KEY: "abc...xyz", TTS_TOTAL_TIMEOUT_SECONDS: "100", TTS_PROVIDER_TIMEOUT_SECONDS: "60",
      MATRIX_HOMESERVER: "http://localhost:8008", MATRIX_ACCESS_TOKEN: "mat...key", MATRIX_TIMEOUT_SECONDS: "30", MATRIX_MAX_TEXT_CHARS: "2000",
      PRINTER_BRIDGE_URL: "http://localhost:9100", PRINTER_ALLOWED_PRINTERS: "test-printer", PRINTER_MAX_COPIES: "10",
      IMAGE_JOBS_PER_CALLER_PER_DAY: "20", POLICY_DEFAULT_ALLOW: "true", ARTIFACT_SIGNED_URL_SECRET: "sig...ret",
      LOCAL_IMAGE_QUALITY_PRESETS: "{}", LOCAL_IMAGE_ALLOWED_STYLES: "default"
    },
    settings_schema: {
      IMAGE_JOBS_PER_CALLER_PER_DAY: { type: "integer", minimum: 0, group: "quotas", zh: "生图额度", en: "Image quota" },
      POLICY_DEFAULT_ALLOW: { type: "boolean", group: "policy", zh: "允许普通工具", en: "Allow regular tools" },
      ARTIFACT_SIGNED_URL_SECRET: { type: "secret", group: "storage", zh: "签名密钥", en: "Signing secret" },
      LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS: { type: "list", group: "localimage", zh: "ComfyUI 域名白名单", en: "ComfyUI host allowlist" },
      LOCAL_IMAGE_QUALITY_PRESETS: { type: "json", group: "localimage", zh: "质量预设", en: "Quality presets" },
      LOCAL_IMAGE_ALLOWED_STYLES: { type: "list", group: "localimage", zh: "风格", en: "Styles", choices: ["default", "photo"] },
      MATRIX_ACCESS_TOKEN: { type: "secret", group: "matrix", zh: "默认 Matrix 密钥", en: "Default Matrix token" }
    },
    agents: [{
      name: "alpha", enabled: true, has_config: true,
      caller: { role: "role_play", gateway_token_configured: true, shared_artifact_read: false },
      matrix: { enabled: true, account: "alpha", homeserver: "http://matrix.test", access_token_configured: true },
      high_risk_tools: ["matrix_send_text"]
    }, {
      name: "beta", enabled: false, caller: { gateway_token_configured: false },
      matrix: { enabled: false, account: "beta" }, high_risk_tools: []
    }],
    environment: { python: { available: true, output: "Python 3.12" }, config_main: { exists: true, path: "config.main.yaml" }, database_path: { exists: true, path: "test.sqlite3" } },
    llm: { providers: [{ id: "provider-1", name: "Test provider", base_url: "https://api.test/v1", key_configured: true, models: [
      { id: "image-model-1", provider_id: "provider-1", model_id: "image-model", tags: ["image"] },
      { id: "text-model-1", provider_id: "provider-1", model_id: "text-model", tags: ["text"] }
    ] }] }
  };
}
async function createUI(t, options = {}) {
  const browserErrors = [], requests = [];
  let status = copy(options.status || fixture());
  let failSave = false, failRefresh = false, holdSave = null;
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => browserErrors.push(error));
  const dom = new JSDOM(html, { url: "http://localhost/webui/", runScripts: "outside-only", virtualConsole });
  const w = dom.window;
  w.matchMedia = () => ({ matches: false, addEventListener() {} });
  w.HTMLElement.prototype.scrollIntoView = function () {};
  w.scrollTo = function () {};
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function () { this.open = false; };
  w.localStorage.setItem("webui.language", "zh-CN");
  if (options.legacyToken) w.localStorage.setItem("webui.adminToken", options.legacyToken);
  const respond = (payload, code = 200) => ({ ok: code < 400, status: code, json: async () => copy(payload) });
  w.fetch = async (url, init = {}) => {
    const body = init.body ? JSON.parse(init.body) : null;
    requests.push({ url, body, init });
    if (url.endsWith("/auth")) return respond({ ok: true, dev_mode: !!options.devMode, login_configured: true });
    if (url.endsWith("/status")) {
      if (failRefresh) throw new Error("offline");
      return respond(status);
    }
    if (url.endsWith("/config")) {
      if (holdSave) await holdSave;
      if (failSave) throw new Error("offline");
      Object.assign(status.local_env, body.owned_fields);
      for (const name of Object.keys(body.owned_fields)) if (/KEY|TOKEN|SECRET/.test(name)) status.local_env[name] = "********";
      if (body.agents) status.agents = body.agents.map((agent) => ({
        ...agent, caller: { ...agent.caller, gateway_token_configured: agent.caller.gateway_token_configured || !!agent.caller.gateway_token },
        matrix: { ...agent.matrix, access_token_configured: agent.matrix.access_token_configured || !!agent.matrix.access_token }
      }));
      return respond({ ok: true });
    }
    const provider = status.llm.providers.find((item) => item.id === (body?.provider_id || body?.id));
    if (url.endsWith("/providers/save")) {
      const id = body.id || "provider-new";
      if (provider) { provider.name = body.name; provider.base_url = body.base_url; }
      else status.llm.providers.push({ id, name: body.name, base_url: body.base_url, key_configured: true, models: [] });
      return respond({ ok: true, provider_id: id, ...status.llm });
    }
    if (url.endsWith("/models/save")) {
      provider.models = body.models.map((model, i) => ({ ...model, id: provider.models.find((old) => old.model_id === model.model_id)?.id || "new-" + i }));
      return respond({ ok: true, ...status.llm });
    }
    if (url.endsWith("/discover")) return respond({ ok: true, models: ["image-model", "text-model", "new-model"] });
    if (url.endsWith("/providers/delete")) {
      status.llm.providers = status.llm.providers.filter((item) => item.id !== body.provider_id);
      return respond({ ok: true, ...status.llm });
    }
    throw new Error("Unexpected request: " + url);
  };
  w.eval(script);
  await tick();
  if (!options.devMode) {
    w.document.querySelector("#adminToken").value = "test-login-key";
    w.document.querySelector("#authForm").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
    await tick();
  }
  const $ = (selector) => w.document.querySelector(selector);
  const input = (selector, value, type = "input") => {
    const node = $(selector); assert.ok(node, "Missing control: " + selector);
    if (node.type === "checkbox") node.checked = value; else node.value = value;
    node.dispatchEvent(new w.Event(type, { bubbles: true }));
  };
  t.after(() => { assert.deepEqual(browserErrors, [], "Unexpected DOM errors"); w.close(); });
  return {
    w, $, input, requests,
    route: (page) => w.routeTo(page),
    click: async (selector) => { assert.ok($(selector), "Missing button: " + selector); $(selector).click(); await tick(); },
    submit: async () => { $("#configForm").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true })); await tick(); },
    saves: () => requests.filter((item) => item.url.endsWith("/config")),
    setFailSave: (value) => { failSave = value; }, setFailRefresh: (value) => { failRefresh = value; },
    holdSave: (promise) => { holdSave = promise; }
  };
}

test("all pages render in both languages and use the latest management fields", async (t) => {
  const ui = await createUI(t);
  for (const lang of ["zh-CN", "en"]) {
    ui.input("#languageSelect", lang, "change");
    for (const page of ["dashboard", "settings", "llm", "image", "localimage", "tts", "matrix", "printer"]) {
      ui.route(page);
      assert.ok(ui.$("#pageTitle").textContent);
      assert.doesNotMatch(ui.$("#pageMount").textContent, /ui\.[a-zA-Z]+|modules\.[a-zA-Z]+/);
      const ids = [...ui.w.document.querySelectorAll("[id]")].map((node) => node.id);
      assert.equal(ids.length, new Set(ids).size, "Duplicate ID on " + page);
    }
  }
  ui.route("localimage"); assert.ok(ui.$('[name="LOCAL_IMAGE_COMFYUI_ALLOWED_HOSTS"]'));
  ui.route("image"); assert.ok(ui.$('select[name="IMAGE_MODEL_ID"]'));
});

test("drafts survive page, theme, language, and switch changes; only changed values are posted", async (t) => {
  const ui = await createUI(t);
  ui.route("tts");
  ui.input('[name="TTS_LOCAL_HTTP_URL"]', "http://new.test/tts");
  ui.input('[name="TTS_API_KEY"]', "replacement-key");
  ui.input('[name="TTS_MODULE_ENABLED"]', true, "change");
  ui.input("#themeSelect", "dark", "change");
  ui.input("#languageSelect", "en", "change");
  ui.route("settings"); ui.input('[name="IMAGE_JOBS_PER_CALLER_PER_DAY"]', "0");
  ui.route("tts");
  assert.equal(ui.$('[name="TTS_API_KEY"]').value, "replacement-key");
  assert.equal(ui.$('[name="TTS_LOCAL_HTTP_URL"]').value, "http://new.test/tts");
  await ui.submit();
  assert.deepEqual(ui.saves()[0].body, { owned_fields: {
    TTS_LOCAL_HTTP_URL: "http://new.test/tts", TTS_API_KEY: "replacement-key", TTS_MODULE_ENABLED: "true", IMAGE_JOBS_PER_CALLER_PER_DAY: "0"
  } });
  assert.equal(ui.$("#saveConfig").disabled, true);
});

test("existing secrets remain untouched and clearing normal fields is explicit", async (t) => {
  const ui = await createUI(t); ui.route("tts");
  assert.equal(ui.$('[name="TTS_API_KEY"]').value, "");
  ui.input('[name="TTS_LOCAL_HTTP_URL"]', "");
  await ui.submit();
  assert.deepEqual(ui.saves()[0].body, { owned_fields: { TTS_LOCAL_HTTP_URL: "" } });
});

test("validation blocks incomplete enabled modules, navigates to fields, and keeps switches enabled", async (t) => {
  const status = fixture(); status.local_env.TTS_LOCAL_HTTP_URL = "";
  const ui = await createUI(t, { status });
  ui.input('[name="TTS_MODULE_ENABLED"]', true, "change");
  await ui.submit();
  assert.equal(ui.saves().length, 0);
  assert.ok(ui.$(".validation-summary"));
  assert.equal(ui.w.document.activeElement.name, "TTS_LOCAL_HTTP_URL");
  assert.equal(ui.$('[name="TTS_MODULE_ENABLED"]').checked, true);
  ui.input('[name="TTS_LOCAL_HTTP_URL"]', "file:///tmp/audio");
  await ui.submit(); assert.equal(ui.saves().length, 0);
  ui.input('[name="TTS_LOCAL_HTTP_URL"]', "http://localhost:9000/tts");
  await ui.submit(); assert.equal(ui.saves().length, 1);
});

test("schema validation accepts zero quotas and catches JSON, list, and numeric errors", async (t) => {
  const ui = await createUI(t); ui.route("settings");
  ui.input('[name="IMAGE_JOBS_PER_CALLER_PER_DAY"]', "-1");
  await ui.submit(); assert.equal(ui.saves().length, 0);
  ui.input('[name="IMAGE_JOBS_PER_CALLER_PER_DAY"]', "0");
  ui.route("localimage"); ui.input('[name="LOCAL_IMAGE_QUALITY_PRESETS"]', "[]");
  await ui.submit(); assert.equal(ui.saves().length, 0); assert.equal(ui.$('[name="LOCAL_IMAGE_QUALITY_PRESETS"]').getAttribute("aria-invalid"), "true");
  ui.input('[name="LOCAL_IMAGE_QUALITY_PRESETS"]', "{}");
  ui.input('[name="LOCAL_IMAGE_ALLOWED_STYLES"]', "unknown");
  await ui.submit(); assert.equal(ui.saves().length, 0);
  ui.input('[name="LOCAL_IMAGE_ALLOWED_STYLES"]', "photo");
  await ui.submit(); assert.equal(ui.saves().length, 1);
});

test("failed saves preserve drafts, successful saves with failed refresh cannot be resubmitted", async (t) => {
  const ui = await createUI(t); ui.route("tts"); ui.input('[name="TTS_API_KEY"]', "new-secret");
  ui.setFailSave(true); await ui.submit();
  assert.equal(ui.$('[name="TTS_API_KEY"]').value, "new-secret");
  assert.equal(ui.$("#saveConfig").disabled, false);
  ui.setFailSave(false); ui.setFailRefresh(true); await ui.submit();
  assert.equal(ui.$("#saveConfig").disabled, true);
  assert.equal(ui.$('[name="TTS_API_KEY"]').value, "");
  assert.match(ui.$("#messageText").textContent, /已保存/);
});

test("duplicate submit is blocked while saving", async (t) => {
  const ui = await createUI(t); ui.route("tts"); ui.input('[name="TTS_API_KEY"]', "new-secret");
  let release; ui.holdSave(new Promise((resolve) => { release = resolve; }));
  await ui.submit(); await ui.submit();
  assert.equal(ui.saves().length, 1); assert.equal(ui.$("#configFields").disabled, true);
  release(); await tick(); assert.equal(ui.$("#saveConfig").disabled, true);
});

test("agent credentials and role persist; Matrix-disabled agents need only gateway credentials", async (t) => {
  const ui = await createUI(t); ui.route("matrix");
  ui.input('[data-agent-field="caller.gateway_token"]', "new-alpha-key");
  ui.input('[data-agent-field="caller.role"]', "admin", "change");
  await ui.click('[data-agent="beta"]');
  ui.input('[data-agent-field="caller.gateway_token"]', "beta-key");
  ui.input('[data-agent-field="enabled"]', true, "change");
  await ui.click('[data-agent="alpha"]');
  assert.equal(ui.$('[data-agent-field="caller.gateway_token"]').value, "new-alpha-key");
  assert.equal(ui.$('[data-agent-field="caller.role"]').value, "admin");
  await ui.submit();
  const agents = ui.saves()[0].body.agents;
  assert.equal(agents[0].matrix.homeserver, "http://matrix.test");
  assert.equal(agents[1].enabled, true);
  assert.equal(agents[1].matrix.enabled, false);
});

test("refresh and discard confirmations protect drafts and cancellation preserves edits", async (t) => {
  const ui = await createUI(t); ui.route("tts"); ui.input('[name="TTS_API_KEY"]', "draft");
  await ui.click("#refreshStatus");
  assert.equal(ui.$("#appDialog").open, true);
  await ui.click("#dialogCancel");
  assert.equal(ui.$('[name="TTS_API_KEY"]').value, "draft");
  await ui.click("#discardDraft"); await ui.click("#dialogConfirm");
  assert.equal(ui.$('[name="TTS_API_KEY"]').value, "");
  assert.equal(ui.$("#saveConfig").disabled, true);
});

test("provider and model drafts survive navigation and config saves; models save through catalog API", async (t) => {
  const ui = await createUI(t); ui.route("llm");
  ui.input("#providerName", "Updated provider");
  ui.input('[data-model-tag="text"][data-model="0"]', true, "change");
  ui.route("tts"); ui.input('[name="TTS_API_KEY"]', "replacement");
  await ui.submit();
  ui.route("llm");
  assert.equal(ui.$("#providerName").value, "Updated provider");
  assert.equal(ui.$('[data-model-tag="text"][data-model="0"]').checked, true);
  await ui.click("#saveProvider");
  await ui.click("#saveModels");
  assert.ok(ui.requests.some((item) => item.url.endsWith("/providers/save") && item.body.name === "Updated provider"));
  assert.deepEqual(ui.requests.find((item) => item.url.endsWith("/models/save")).body.models[0].tags, ["image", "text"]);
});

test("model search, manual add, discovery, and selection work without saving unrelated drafts", async (t) => {
  const ui = await createUI(t); ui.route("llm");
  ui.input("#modelSearch", "none"); assert.equal(ui.$("#noModels").hidden, false);
  ui.input("#manualModel", "manual-image"); await ui.click("#addManualModel");
  assert.match(ui.$(".model-list").textContent, /manual-image/);
  await ui.click("#fetchModels");
  assert.match(ui.$(".model-list").textContent, /new-model/);
  await ui.click("#saveModels");
  const body = ui.requests.find((item) => item.url.endsWith("/models/save")).body;
  assert.ok(body.models.some((model) => model.model_id === "manual-image"));
  assert.ok(!body.models.some((model) => model.model_id === "new-model"));
  assert.equal(ui.saves().length, 0);
});

test("legacy admin tokens are cleared; login keys use session storage; dev mode needs no key", async (t) => {
  const ui = await createUI(t, { legacyToken: "old-admin-token" });
  assert.equal(ui.w.localStorage.getItem("webui.adminToken"), null);
  assert.equal(ui.w.sessionStorage.getItem("webui.loginKey"), "test-login-key");
  const dev = await createUI(t, { devMode: true });
  assert.equal(dev.$("#authPanel").hidden, true);
  assert.equal(dev.$("#disconnect").hidden, true);
});

test("Agent creation validates names and duplicate entries; removal can be cancelled", async (t) => {
  const ui = await createUI(t); ui.route("matrix");
  await ui.click("[data-add-agent]");
  ui.input("#dialogInput", "bad name");
  await ui.click("#dialogConfirm");
  assert.equal(ui.$("#appDialog").open, true);
  assert.ok(ui.$("#dialogError").textContent);
  ui.input("#dialogInput", "alpha"); await ui.click("#dialogConfirm");
  assert.equal(ui.$("#appDialog").open, true);
  ui.input("#dialogInput", "gamma"); await ui.click("#dialogConfirm");
  assert.ok(ui.$('[data-agent="gamma"]'));
  await ui.click("[data-remove-agent]"); await ui.click("#dialogCancel");
  assert.ok(ui.$('[data-agent="gamma"]'));
  await ui.click("[data-remove-agent]"); await ui.click("#dialogConfirm");
  assert.equal(ui.$('[data-agent="gamma"]'), null);
});

test("workflow replacement requires confirmation and preserves unrelated drafts", async (t) => {
  const ui = await createUI(t); ui.route("localimage");
  ui.input('[name="LOCAL_IMAGE_COMFYUI_BASE_URL"]', "http://comfy.test:8188");
  await ui.click('[data-workflow="anima"]'); await ui.click("#dialogCancel");
  assert.equal(ui.$('[name="LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH"]').value, "./custom.json");
  await ui.click('[data-workflow="anima"]'); await ui.click("#dialogConfirm");
  assert.match(ui.$('[name="LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH"]').value, /anima/);
  assert.equal(ui.$('[name="LOCAL_IMAGE_COMFYUI_BASE_URL"]').value, "http://comfy.test:8188");
  ui.route("tts"); ui.route("localimage");
  assert.equal(ui.$('[data-workflow="anima"]').getAttribute("aria-pressed"), "true");
});

test("keyboard focus stays on toggles and reverting edits clears the dirty state", async (t) => {
  const ui = await createUI(t);
  ui.$("#toggle-tts").focus();
  ui.input("#toggle-tts", true, "change");
  assert.equal(ui.w.document.activeElement.id, "toggle-tts");
  ui.input("#toggle-tts", false, "change");
  assert.equal(ui.$("#saveConfig").disabled, true);
  ui.route("matrix");
  ui.input('[data-tool="matrix_send_image"]', true, "change");
  ui.input('[data-tool="matrix_send_image"]', false, "change");
  assert.equal(ui.$("#saveConfig").disabled, true);
});
