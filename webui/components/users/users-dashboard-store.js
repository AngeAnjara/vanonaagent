import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";

export const store = createStore("usersDashboardStore", {
  // State
  users: [],
  selectedUser: null,
  userChats: [],
  formMode: null, // null | 'create' | 'edit' | 'delete'
  formData: { id: null, username: "", password: "", role: "user" },
  currentUser: null,
  validationErrors: {},
  statusMessage: null,
  statusType: null, // 'success' | 'error' | 'info'
  loading: false,
  loadingChats: false,
  isTesting: false,
  error: null,
  currentPage: 1,
  itemsPerPage: 10,
  chatFilters: { type: "", dateFrom: "", dateTo: "" },

  // Lifecycle
  async onOpen() {
    await this.loadUsers();
  },
  cleanup() {
    this.users = [];
    this.selectedUser = null;
    this.userChats = [];
    this.formMode = null;
    this.formData = { id: null, username: "", password: "", role: "user" };
    this.currentUser = null;
    this.validationErrors = {};
    this.statusMessage = null;
    this.statusType = null;
    this.loading = false;
    this.loadingChats = false;
    this.isTesting = false;
    this.error = null;
    this.currentPage = 1;
    this.itemsPerPage = 10;
    this.chatFilters = { type: "", dateFrom: "", dateTo: "" };
  },

  // Getters
  get totalPages() {
    return Math.ceil((this.users?.length || 0) / this.itemsPerPage) || 1;
  },
  get paginatedUsers() {
    const start = (this.currentPage - 1) * this.itemsPerPage;
    return (this.users || []).slice(start, start + this.itemsPerPage);
  },
  get filteredChats() {
    let list = this.userChats || [];
    if (this.chatFilters.type) {
      list = list.filter((c) => (c.type || "").toLowerCase() === this.chatFilters.type);
    }
    // simple date filters if provided (ISO strings)
    if (this.chatFilters.dateFrom) {
      const from = new Date(this.chatFilters.dateFrom);
      list = list.filter((c) => (c.created_at ? new Date(c.created_at) >= from : true));
    }
    if (this.chatFilters.dateTo) {
      const to = new Date(this.chatFilters.dateTo);
      list = list.filter((c) => (c.created_at ? new Date(c.created_at) <= to : true));
    }
    return list;
  },

  // Helpers
  clearStatus() {
    this.statusMessage = null;
    this.statusType = null;
  },
  formatDate(iso) {
    try {
      return iso ? new Date(iso).toLocaleString() : "";
    } catch {
      return iso || "";
    }
  },

  // Users
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
    this.formData = { id: null, username: '', password: '', role: 'user' };
    this.formMode = 'create';
  },
  openEditForm(user) {
    this.clearStatus();
    this.validationErrors = {};
    this.currentUser = user;
    this.formData = { id: user.id, username: user.username, password: '', role: user.role };
    this.formMode = 'edit';
  },
  openDeleteConfirm(user) {
    this.clearStatus();
    this.currentUser = user;
    this.formMode = 'delete';
  },
  closeForm() {
    this.formMode = null;
    this.currentUser = null;
    this.validationErrors = {};
    this.clearStatus();
    this.formData = { id: null, username: '', password: '', role: 'user' };
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
        this.statusMessage = "Création réussie mais l'identifiant (ID) est manquant dans la réponse.";
        this.statusType = 'error';
        return;
      }
      await this.loadUsers();
      this.statusMessage = 'Utilisateur créé avec succès';
      this.statusType = 'success';
      // switch to edit with ID and clear password
      this.formData.id = res.user.id;
      this.formData.password = '';
      this.formMode = 'edit';
    } catch (e) {
      this.statusMessage = e.message || "Erreur lors de la création de l'utilisateur";
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

  // Chats
  async viewUserChats(user) {
    this.selectedUser = user;
    await this.loadUserChats(user?.username);
  },
  async loadUserChats(username) {
    if (!username) return;
    this.loadingChats = true;
    this.userChats = [];
    try {
      const res = await callJsonApi('/user_chats_api', { username });
      if (!res || res.success === false) {
        this.statusMessage = (res && res.error) ? res.error : 'Erreur lors du chargement des chats';
        this.statusType = 'error';
        this.userChats = [];
        return;
      }
      this.statusMessage = null;
      this.statusType = null;
      this.userChats = res.chats || [];
    } catch (e) {
      this.statusMessage = e.message || 'Erreur lors du chargement des chats';
      this.statusType = 'error';
    } finally {
      this.loadingChats = false;
    }
  },
  backToUsersList() {
    this.selectedUser = null;
    this.userChats = [];
    this.chatFilters = { type: '', dateFrom: '', dateTo: '' };
  },
  async deleteUserChat(chatId) {
    try {
      const res = await callJsonApi('/user_chat_delete_api', { id: chatId });
      if (!res || res.success === false) {
        this.statusMessage = (res && res.error) ? res.error : 'Échec de la suppression du chat';
        this.statusType = 'error';
        return;
      }
      this.statusMessage = 'Chat supprimé';
      this.statusType = 'success';
      if (this.selectedUser?.username) await this.loadUserChats(this.selectedUser.username);
    } catch (e) {
      this.statusMessage = e.message || 'Suppression de chat non disponible';
      this.statusType = 'error';
    }
  },

  openChat(chat) {
    const id = chat?.id;
    if (!id) return;
    try {
      if (globalThis.selectChat) globalThis.selectChat(id);
      if (globalThis.closeModal) globalThis.closeModal();
    } catch (e) {
      // swallow errors, show toast-like message
      this.statusMessage = 'Impossible d\'ouvrir le chat';
      this.statusType = 'error';
    }
  },
});
