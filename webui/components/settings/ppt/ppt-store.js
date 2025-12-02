import { createStore } from "/js/AlpineStore.js";

const model = {
  enabled: false,
  defaultFormat: "pptx",
  defaultTheme: "modern",
  chartLibrary: "chartjs",
  enablePreview: true,
  isSaving: false,
  isTesting: false,
  statusMessage: "",
  statusType: "info",

  async init() {
    await this.loadFromSettings();
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
      const section = sections.find((s) => s.id === "ppt");
      if (!section || !section.fields) {
        this.statusMessage = "PowerPoint settings section not found.";
        this.statusType = "error";
        return;
      }
      const getField = (id) => section.fields.find((f) => f.id === id) || { value: "" };
      this.enabled = !!getField("ppt_enabled").value;
      this.defaultFormat = getField("ppt_default_format").value || "pptx";
      this.defaultTheme = getField("ppt_default_theme").value || "modern";
      this.chartLibrary = getField("ppt_chart_library").value || "chartjs";
      this.enablePreview = !!getField("ppt_enable_preview").value;
    } catch (err) {
      console.error("Error loading PowerPoint settings", err);
      this.statusMessage = "Error loading PowerPoint settings.";
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
      let section = sections.find((s) => s.id === "ppt");
      if (!section) {
        section = { id: "ppt", fields: [], tab: "integrations" };
        sections.push(section);
      }
      if (!section.fields) section.fields = [];
      const setField = (id, value) => {
        const field = section.fields.find((f) => f.id === id);
        if (field) {
          field.value = value;
        } else {
          section.fields.push({ id, value });
        }
      };

      setField("ppt_enabled", this.enabled);
      setField("ppt_default_format", this.defaultFormat);
      setField("ppt_default_theme", this.defaultTheme);
      setField("ppt_chart_library", this.chartLibrary);
      setField("ppt_enable_preview", this.enablePreview);

      const saveResp = await fetchApi("/settings_set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settingsPayload),
      });
      const saveData = await saveResp.json();
      if (saveData && saveData.settings) {
        this.statusMessage = "PowerPoint settings saved successfully.";
        this.statusType = "success";
        await this.loadFromSettings();
        if (window && window.toastFrontendInfo)
          window.toastFrontendInfo("PowerPoint settings saved.", "PowerPoint");
      } else {
        this.statusMessage = "Failed to save PowerPoint settings.";
        this.statusType = "error";
        if (window && window.toastFrontendError)
          window.toastFrontendError("Failed to save PowerPoint settings.", "PowerPoint");
      }
    } catch (err) {
      console.error("Error saving PowerPoint settings", err);
      this.statusMessage = "Error saving PowerPoint settings.";
      this.statusType = "error";
      if (window && window.toastFrontendError)
        window.toastFrontendError("Error saving PowerPoint settings.", "PowerPoint");
    } finally {
      this.isSaving = false;
    }
  },

  async testConnection() {
    this.isTesting = true;
    this.statusMessage = "";
    this.statusType = "info";
    try {
      const resp = await fetchApi("/ppt_test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await resp.json();
      if (data.success) {
        this.statusMessage = data.message || "Libraries available.";
        this.statusType = "success";
        if (window && window.toastFrontendInfo)
          window.toastFrontendInfo(this.statusMessage, "PowerPoint");
      } else {
        this.statusMessage = data.message || "Library test failed.";
        this.statusType = "error";
        if (window && window.toastFrontendError)
          window.toastFrontendError(this.statusMessage, "PowerPoint");
      }
    } catch (err) {
      console.error("Error testing PowerPoint libraries", err);
      this.statusMessage = "Error testing PowerPoint libraries.";
      this.statusType = "error";
      if (window && window.toastFrontendError)
        window.toastFrontendError("Error testing PowerPoint libraries.", "PowerPoint");
    } finally {
      this.isTesting = false;
    }
  },
};

const store = createStore("pptStore", model);
export { store };
