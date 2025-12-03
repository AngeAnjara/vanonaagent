import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";

const store = createStore('userManagementStore', {
  users: [],
  loading: false,
  showCreateModal: false,
  showEditModal: false,
  showDeleteModal: false,
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

  openCreateModal() {
    this.formData = { username: '', password: '', role: 'user', id: null };
    this.showCreateModal = true;
  },

  openEditModal(user) {
    this.currentUser = user;
    this.formData = { username: user.username, password: '', role: user.role, id: user.id };
    this.showEditModal = true;
  },

  openDeleteModal(user) {
    this.currentUser = user;
    this.showDeleteModal = true;
  },

  async createUser() {
    if (!this.formData.username || !this.formData.password) {
      this.error = "Nom d'utilisateur et mot de passe requis";
      return;
    }
    try {
      this.loading = true;
      await callJsonApi('/user_management_api', {
        action: 'create',
        username: this.formData.username,
        password: this.formData.password,
        role: this.formData.role,
      });
      this.closeModals();
      await this.loadUsers();
    } catch (e) {
      this.error = e.message || 'Erreur lors de la création de l\'utilisateur';
    } finally {
      this.loading = false;
    }
  },

  async updateUser() {
    if (!this.formData.id) return;
    try {
      this.loading = true;
      await callJsonApi('/user_management_api', {
        action: 'update',
        id: this.formData.id,
        role: this.formData.role,
        password: this.formData.password || undefined,
      });
      this.closeModals();
      await this.loadUsers();
    } catch (e) {
      this.error = e.message || 'Erreur lors de la mise à jour';
    } finally {
      this.loading = false;
    }
  },

  async deleteUser() {
    if (!this.currentUser) return;
    try {
      this.loading = true;
      await callJsonApi('/user_management_api', {
        action: 'delete',
        id: this.currentUser.id,
      });
      this.closeModals();
      await this.loadUsers();
    } catch (e) {
      this.error = e.message || 'Erreur lors de la suppression';
    } finally {
      this.loading = false;
    }
  },

  closeModals() {
    this.showCreateModal = false;
    this.showEditModal = false;
    this.showDeleteModal = false;
    this.currentUser = null;
    this.error = null;
    this.formData = { username: '', password: '', role: 'user', id: null };
  },

  async init() {
    await this.loadUsers();
  }
});

export { store };
