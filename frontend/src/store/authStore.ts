import { create } from "zustand";

import api from "@/lib/api";
import keycloak from "@/lib/keycloak";
import type { CurrentUser } from "@/types";

interface AuthState {
  user: CurrentUser | null;
  isLoading: boolean;

  loadCurrentUser: () => Promise<void>;
  clearUser: () => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,

  loadCurrentUser: async () => {
    try {
      set({ isLoading: true });

      const { data } = await api.get<CurrentUser>("/identity/me");

      set({
        user: data,
        isLoading: false,
      });
    } catch (error) {
      set({
        user: null,
        isLoading: false,
      });

      throw error;
    }
  },

  clearUser: () =>
    set({
      user: null,
    }),

  logout: () => {
    set({ user: null });
    // Keycloak owns the session; this clears its cookie and bounces back to the SPA
    // root, where main.tsx's login-required init redirects to the hosted login page.
    void keycloak.logout({ redirectUri: window.location.origin });
  },
}));