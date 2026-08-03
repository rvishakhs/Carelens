import { create } from "zustand";

import api from "@/lib/api";
import type { CurrentUser } from "@/types";

interface AuthState {
  user: CurrentUser | null;
  isLoading: boolean;

  loadCurrentUser: () => Promise<void>;
  clearUser: () => void;
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
}));