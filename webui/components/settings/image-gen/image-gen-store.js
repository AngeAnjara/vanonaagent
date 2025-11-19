import { createStore } from "/js/AlpineStore.js";

const model = {
  enabled: false,
  apiKey: "",
  model: "seedance",
  width: 1024,
  height: 1024,
  steps: 30,
  batchSize: 5,
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
      const section = sections.find((s) => s.id === "image_gen");
      if (!section || !section.fields) {
        this.statusMessage = "Image Generation settings section not found.";
        this.statusType = "error";
        return;
      }
      const getField = (id) => section.fields.find((f) => f.id === id) || { value: "" };
      this.enabled = !!getField("image_gen_enabled").value;
      this.apiKey = getField("image_gen_api_key").value || "";
      this.model = getField("image_gen_model").value || "seedance";
      this.width = Number(getField("image_gen_default_width").value || 1024);
      this.height = Number(getField("image_gen_default_height").value || 1024);
      this.steps = Number(getField("image_gen_default_steps").value || 30);
      this.batchSize = Number(getField("image_gen_batch_size").value || 5);
    } catch (err) {
      console.error("Error loading Image Generation settings", err);
      this.statusMessage = "Error loading Image Generation settings.";
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
      let section = sections.find((s) => s.id === "image_gen");
      if (!section) {
        section = { id: "image_gen", fields: [], tab: "integrations" };
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

      setField("image_gen_enabled", this.enabled);
      setField("image_gen_api_key", this.apiKey || "");
      setField("image_gen_model", this.model);
      setField("image_gen_default_width", this.width);
      setField("image_gen_default_height", this.height);
      setField("image_gen_default_steps", this.steps);
      setField("image_gen_batch_size", this.batchSize);

      const saveResp = await fetchApi("/settings_set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settingsPayload),
      });
      const saveData = await saveResp.json();
      if (saveData && saveData.settings) {
        this.statusMessage = "Image Generation settings saved successfully.";
        this.statusType = "success";
        await this.loadFromSettings();
        if (window && window.toastFrontendInfo)
          window.toastFrontendInfo("Image Generation settings saved.", "Image Generation");
      } else {
        this.statusMessage = "Failed to save Image Generation settings.";
        this.statusType = "error";
        if (window && window.toastFrontendError)
          window.toastFrontendError("Failed to save Image Generation settings.", "Image Generation");
      }
    } catch (err) {
      console.error("Error saving Image Generation settings", err);
      this.statusMessage = "Error saving Image Generation settings.";
      this.statusType = "error";
      if (window && window.toastFrontendError)
        window.toastFrontendError("Error saving Image Generation settings.", "Image Generation");
    } finally {
      this.isSaving = false;
    }
  },

  async testConnection() {
    this.isTesting = true;
    this.statusMessage = "";
    this.statusType = "info";
    try {
      const resp = await fetchApi("/image_gen_test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: this.apiKey, model: this.model }),
      });
      const data = await resp.json();
      if (data.success) {
        this.statusMessage = data.message || "WaveSpeed connection successful.";
        this.statusType = "success";
        if (window && window.toastFrontendInfo)
          window.toastFrontendInfo(this.statusMessage, "Image Generation");
      } else {
        this.statusMessage = data.message || "WaveSpeed connection failed.";
        this.statusType = "error";
        if (window && window.toastFrontendError)
          window.toastFrontendError(this.statusMessage, "Image Generation");
      }
    } catch (err) {
      console.error("Error testing WaveSpeed connection", err);
      this.statusMessage = "Error testing WaveSpeed connection.";
      this.statusType = "error";
      if (window && window.toastFrontendError)
        window.toastFrontendError("Error testing WaveSpeed connection.", "Image Generation");
    } finally {
      this.isTesting = false;
    }
  },
};

const store = createStore("imageGenStore", model);
export { store };
