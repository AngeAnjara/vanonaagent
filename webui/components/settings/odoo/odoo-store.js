import { createStore } from "/js/AlpineStore.js";

const model = {
  enabled: false,
  url: "",
  db: "",
  user: "",
  password: "",
  isSaving: false,
  isTesting: false,
  statusMessage: "",
  statusType: "info",
  availableModels: [],
  fieldDiscoveryStatus: "unknown",

  async init() {
    await this.loadFromSettings();
  },

  async copyModelName(modelName) {
    try {
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(modelName);
        if (window && window.toastFrontendInfo) {
          window.toastFrontendInfo(`Model '${modelName}' copied to clipboard.`, "Odoo Model");
        }
      }
    } catch (err) {
      console.error("Failed to copy model name", err);
      if (window && window.toastFrontendError) {
        window.toastFrontendError("Failed to copy model name.", "Odoo Model");
      }
    }
  },

  async copyFieldsToClipboard(modelName) {
    try {
      const entry = this.availableModels.find((m) => m.model === modelName);
      if (!entry || !Array.isArray(entry.sample_fields)) {
        return;
      }

      const fieldNames = entry.sample_fields.map((f) => f.name);
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(JSON.stringify(fieldNames));
        if (window && window.toastFrontendInfo) {
          window.toastFrontendInfo(`Fields for '${modelName}' copied to clipboard.`, "Odoo Fields");
        }
      }
    } catch (err) {
      console.error("Failed to copy fields", err);
      if (window && window.toastFrontendError) {
        window.toastFrontendError("Failed to copy fields.", "Odoo Fields");
      }
    }
  },

  getFieldLabel(field) {
    if (!field) return "";
    const name = field.name || "";
    const type = field.type || "";
    const requiredMark = field.required ? " *" : "";
    return `${name} (${type})${requiredMark}`;
  },

  async loadFromSettings() {
    try {
      const response = await fetchApi("/settings_get", { method: "GET" });
      const data = await response.json();

      if (!data || !data.settings || !data.settings.sections) {
        this.statusMessage = "Failed to load settings.";
        this.statusType = "error";
        return;
      }

      const sections = data.settings.sections;
      const odooSection = sections.find((s) => s.id === "odoo");

      if (!odooSection || !odooSection.fields) {
        this.statusMessage = "Odoo settings section not found.";
        this.statusType = "error";
        return;
      }

      const getField = (id) =>
        odooSection.fields.find((f) => f.id === id) || { value: "" };

      this.enabled = !!getField("odoo_enabled").value;
      this.url = getField("odoo_url").value || "";
      this.db = getField("odoo_db").value || "";
      this.user = getField("odoo_user").value || "";

      this.password = getField("odoo_password").value || "";
    } catch (err) {
      console.error("Error loading Odoo settings", err);
      this.statusMessage = "Error loading Odoo settings.";
      this.statusType = "error";
    }
  },

  async saveSettings() {
    this.isSaving = true;
    this.statusMessage = "";
    this.statusType = "info";

    try {
      const response = await fetchApi("/settings_get", { method: "GET" });
      const data = await response.json();

      if (!data || !data.settings || !data.settings.sections) {
        throw new Error("Invalid settings format from server");
      }

      const settingsPayload = data.settings;
      const sections = settingsPayload.sections;
      const odooSection = sections.find((s) => s.id === "odoo");

      if (!odooSection || !odooSection.fields) {
        throw new Error("Odoo settings section not found");
      }

      const setField = (id, value) => {
        const field = odooSection.fields.find((f) => f.id === id);
        if (field) {
          field.value = value;
        } else {
          odooSection.fields.push({ id, value });
        }
      };

      setField("odoo_enabled", this.enabled);
      setField("odoo_url", this.url);
      setField("odoo_db", this.db);
      setField("odoo_user", this.user);
      setField("odoo_password", this.password || "");

      const saveResp = await fetchApi("/settings_set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settingsPayload),
      });

      const saveData = await saveResp.json();
      if (saveData && saveData.settings) {
        this.statusMessage = "Odoo settings saved successfully.";
        this.statusType = "success";
        await this.loadFromSettings();
        window.toastFrontendInfo("Odoo settings saved.", "Odoo Settings");
      } else {
        this.statusMessage = "Failed to save Odoo settings.";
        this.statusType = "error";
        window.toastFrontendError("Failed to save Odoo settings.", "Odoo Settings");
      }
    } catch (err) {
      console.error("Error saving Odoo settings", err);
      this.statusMessage = "Error saving Odoo settings.";
      this.statusType = "error";
      window.toastFrontendError("Error saving Odoo settings.", "Odoo Settings");
    } finally {
      this.isSaving = false;
    }
  },

  clearAvailableModels() {
    this.availableModels = [];
    this.fieldDiscoveryStatus = "unknown";
  },

  async testConnection() {
    this.isTesting = true;
    this.statusMessage = "";
    this.statusType = "info";
    this.clearAvailableModels();

    try {
      const resp = await fetchApi("/odoo_test_connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: this.url,
          db: this.db,
          user: this.user,
          // Password is loaded server-side from secure storage
        }),
      });

      const data = await resp.json();
      if (data.success) {
        this.statusMessage = data.message || "Connection successful.";
        this.statusType = "success";

        if (Array.isArray(data.available_models)) {
          this.availableModels = data.available_models;
        } else {
          this.availableModels = [];
        }

        this.fieldDiscoveryStatus = data.field_discovery_status || "unknown";

        window.toastFrontendInfo(this.statusMessage, "Odoo Connection");
      } else {
        this.statusMessage = data.message || "Connection failed.";
        this.statusType = "error";
        window.toastFrontendError(this.statusMessage, "Odoo Connection");
      }
    } catch (err) {
      console.error("Error testing Odoo connection", err);
      this.statusMessage = "Error testing Odoo connection.";
      this.statusType = "error";
      window.toastFrontendError("Error testing Odoo connection.", "Odoo Connection");
    } finally {
      this.isTesting = false;
    }
  },
};

const store = createStore("odooStore", model);

export { store };
