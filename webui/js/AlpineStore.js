// Track all created stores
const stores = new Map();

/**
 * Creates a store that can be used to share state between components.
 * Uses initial state object and returns a proxy to it that uses Alpine when initialized
 * @template T
 * @param {string} name
 * @param {T} initialState
 * @returns {T}
 */
export function createStore(name, initialState) {
  const proxy = new Proxy(initialState, {
    set(target, prop, value) {
      const store = globalThis.Alpine?.store(name);
      if (store) store[prop] = value;
      else target[prop] = value;
      return true;
    },
    get(target, prop) {
      const store = globalThis.Alpine?.store(name);
      if (store) return store[prop];
      return target[prop];
    }
  });

  if (globalThis.Alpine) {
    globalThis.Alpine.store(name, initialState);
  } else {
    document.addEventListener("alpine:init", () => Alpine.store(name, initialState));
  }

  // Store the proxy
  stores.set(name, proxy);

  return /** @type {T} */ (proxy); // explicitly cast for linter support
}

/**
 * Get an existing store by name
 * @template T
 * @param {string} name
 * @returns {T | undefined}
 */
export function getStore(name) {
  return /** @type {T | undefined} */ (stores.get(name));
}

// Auth store for user identity and role-based UI toggles
// Initialized when Alpine is ready
document.addEventListener("alpine:init", async () => {
  try {
    const { callJsonApi } = await import("/js/api.js");
    const initial = {
      username: null,
      role: null,
      isAdmin: false,
      isAuthenticated: false,
      async loadCurrentUser() {
        try {
          const res = await callJsonApi('/current_user_get', {});
          const u = res?.user || {};
          this.setUser(u.username || null, u.role || null);
        } catch (_e) {
          // ignore
        }
      },
      setUser(username, role) {
        this.username = username;
        this.role = role;
        this.isAdmin = role === 'admin';
        this.isAuthenticated = !!username;
      },
      logout() {
        window.location.href = '/logout';
      },
    };
    Alpine.store('auth', initial);
    // Load current user on init
    queueMicrotask(() => Alpine.store('auth')?.loadCurrentUser?.());
  } catch (e) {
    // no-op if api.js isn't available yet
  }
});