import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";

const store = createStore('userManagementStore', {
  users: [],
  loading: false,
  formMode: null, // null | 'create' | 'edit' | 'delete'
  isTesting: false,
  testResult: null,
  statusMessage: null,
  statusType: null, // 'success' | 'error' | 'info'
  validationErrors: {},
  currentUser: null,
  formData: { username: '', password: '', role: 'user', id: null },
  error: null,

  async loadUsers() {
    try {
      this.loading = true;
      const res = await callJsonApi('/user_management_api', { action: 'list' });
      this.users = res.users || [];
    } catch (e) {
      this.error = e.message || 'Erreur lors du chargement des utilisateurs';
    } finally {
      this.loading = false;
    }
  },

  openCreateForm() {
    this.clearStatus();
    this.validationErrors = {};
    this.formData = { username: '', password: '', role: 'user', id: null };
    this.formMode = 'create';
  },

  openEditForm(user) {
    this.clearStatus();
    this.validationErrors = {};
    this.currentUser = user;
    this.formData = { username: user.username, password: '', role: user.role, id: user.id };
    this.formMode = 'edit';
  },

  openDeleteConfirm(user) {
    this.clearStatus();
    this.currentUser = user;
    this.formMode = 'delete';
  },

  async createUser() {
    this.clearStatus();
    if (!this.validateForm('create')) return;
    try {
      this.loading = true;
      const res = await callJsonApi('/user_management_api', {
        action: 'create',
        username: this.formData.username,
        password: this.formData.password,
        role: this.formData.role,
      });
      if (!res || !res.user || !res.user.id) {
        this.statusMessage = "Création réussie mais l'identifiant (ID) est manquant dans la réponse. Impossible d'ouvrir le formulaire d'édition.";
        this.statusType = 'error';
        return;
      }
      await this.loadUsers();
      this.statusMessage = 'Utilisateur créé avec succès';
      this.statusType = 'success';
      // Stay on form in edit mode to allow testing, with reliable ID
      this.formData.password = '';
      this.formData.id = res.user.id;
      this.formMode = 'edit';
    } catch (e) {
      this.statusMessage = e.message || 'Erreur lors de la création de l\'utilisateur';
      this.statusType = 'error';
    } finally {
      this.loading = false;
    }
  },

  async updateUser() {
    if (!this.formData.id) return;
    this.clearStatus();
    if (!this.validateForm('edit')) return;
    try {
      this.loading = true;
      await callJsonApi('/user_management_api', {
        action: 'update',
        id: this.formData.id,
        role: this.formData.role,
        password: this.formData.password || undefined,
      });
      await this.loadUsers();
      this.statusMessage = 'Utilisateur mis à jour';
      this.statusType = 'success';
      this.formData.password = '';
    } catch (e) {
      this.statusMessage = e.message || 'Erreur lors de la mise à jour';
      this.statusType = 'error';
    } finally {
      this.loading = false;
    }
  },

  async deleteUser() {
    if (!this.currentUser) return;
    this.clearStatus();
    try {
      this.loading = true;
      await callJsonApi('/user_management_api', {
        action: 'delete',
        id: this.currentUser.id,
      });
      await this.loadUsers();
      this.statusMessage = 'Utilisateur supprimé';
      this.statusType = 'success';
      this.closeForm();
    } catch (e) {
      this.statusMessage = e.message || 'Erreur lors de la suppression';
      this.statusType = 'error';
    } finally {
      this.loading = false;
    }
  },

  closeForm() {
    this.formMode = null;
    this.currentUser = null;
    this.error = null;
    this.validationErrors = {};
    this.clearStatus();
    this.formData = { username: '', password: '', role: 'user', id: null };
  },

  validateForm(mode) {
    const errs = {};
    const name = (this.formData.username || '').trim();
    if (!name) errs.username = "Le nom d'utilisateur est requis";
    if (name.includes(' ')) errs.username = (errs.username ? errs.username + ' ' : '') + "Pas d'espaces autorisés";
    if (mode === 'create') {
      const pw = this.formData.password || '';
      if (!pw) errs.password = 'Mot de passe requis';
      else if (pw.length < 6) errs.password = 'Au moins 6 caractères';
    } else if (mode === 'edit') {
      const pw = this.formData.password || '';
      if (pw && pw.length < 6) errs.password = 'Au moins 6 caractères';
    }
    if (!['admin','user'].includes(this.formData.role)) errs.role = 'Rôle invalide';
    this.validationErrors = errs;
    return Object.keys(errs).length === 0;
  },

  async testCredentials() {
    if (!this.formData?.password) {
      this.statusMessage = 'Veuillez saisir un mot de passe pour tester';
      this.statusType = 'error';
      return;
    }
    if (!this.formData?.id) return;
    this.clearStatus();
    try {
      this.isTesting = true;
      const res = await callJsonApi('/user_test_credentials', {
        username: this.formData.username,
        password: this.formData.password,
      });
      this.testResult = res;
      if (res.success) {
        this.statusMessage = res.message || 'Identifiants valides';
        this.statusType = 'success';
      } else {
        this.statusMessage = res.message || 'Identifiants invalides';
        this.statusType = 'error';
      }
    } catch (e) {
      this.statusMessage = e.message || 'Erreur lors du test';
      this.statusType = 'error';
    } finally {
      this.isTesting = false;
    }
  },

  clearStatus() {
    this.statusMessage = null;
    this.statusType = null;
    this.testResult = null;
  },

  async init() {
    await this.loadUsers();
  }
});

export { store };
