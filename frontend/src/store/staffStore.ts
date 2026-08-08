import { create } from "zustand";

import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import type { Staff, StaffCreateInput, StaffCreated } from "@/types";

interface StaffState {
  staff: Staff[];
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;
  /** The account just created -- specifically its one-time temporary_password, which
   * the backend never returns from anywhere else. Cleared explicitly via
   * dismissLastCreated once the manager has seen/copied it. */
  lastCreated: StaffCreated | null;

  fetchStaff: () => Promise<void>;
  createStaff: (input: StaffCreateInput) => Promise<void>;
  dismissLastCreated: () => void;
}

export const useStaffStore = create<StaffState>((set) => ({
  staff: [],
  isLoading: false,
  isCreating: false,
  error: null,
  lastCreated: null,

  fetchStaff: async () => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await api.get<Staff[]>("/identity/staff");
      set({ staff: data, isLoading: false });
    } catch (error) {
      set({ isLoading: false, error: extractErrorMessage(error, "Couldn't load staff. Please try again.") });
    }
  },

  createStaff: async (input) => {
    set({ isCreating: true, error: null });
    try {
      const { data } = await api.post<StaffCreated>("/identity/staff", input);
      set((state) => ({
        isCreating: false,
        lastCreated: data,
        staff: [
          ...state.staff,
          { id: data.id, email: data.email, display_name: data.display_name, role: data.role, is_active: true },
        ],
      }));
    } catch (error) {
      set({ isCreating: false });
      throw new Error(extractErrorMessage(error, "Couldn't create this staff member. Please try again."));
    }
  },

  dismissLastCreated: () => set({ lastCreated: null }),
}));
