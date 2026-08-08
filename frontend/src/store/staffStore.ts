import { create } from "zustand";

import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import type { Staff, StaffCreateInput, StaffCreated, StaffCredentials, StaffUpdateInput } from "@/types";

interface StaffState {
  staff: Staff[];
  isLoading: boolean;
  isCreating: boolean;
  /** id of the staff member currently being updated/reset -- lets the list show a
   * spinner on just that row's button instead of disabling the whole page. */
  mutatingId: string | null;
  error: string | null;
  /** The password to show once, from whichever of createStaff/resetPassword ran last
   * -- neither the backend nor this store persists it anywhere else. */
  lastCredentials: { displayName: string; temporaryPassword: string } | null;

  fetchStaff: () => Promise<void>;
  createStaff: (input: StaffCreateInput) => Promise<void>;
  updateStaff: (id: string, input: StaffUpdateInput) => Promise<void>;
  resetPassword: (id: string) => Promise<void>;
  dismissCredentials: () => void;
}

export const useStaffStore = create<StaffState>((set) => ({
  staff: [],
  isLoading: false,
  isCreating: false,
  mutatingId: null,
  error: null,
  lastCredentials: null,

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
        lastCredentials: { displayName: data.display_name, temporaryPassword: data.temporary_password },
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

  updateStaff: async (id, input) => {
    set({ mutatingId: id, error: null });
    try {
      const { data } = await api.patch<Staff>(`/identity/staff/${id}`, input);
      set((state) => ({
        mutatingId: null,
        staff: state.staff.map((member) => (member.id === id ? data : member)),
      }));
    } catch (error) {
      set({
        mutatingId: null,
        error: extractErrorMessage(error, "Couldn't update this staff member. Please try again."),
      });
    }
  },

  resetPassword: async (id) => {
    set({ mutatingId: id, error: null });
    try {
      const { data } = await api.post<StaffCredentials>(`/identity/staff/${id}/reset-password`);
      set({
        mutatingId: null,
        lastCredentials: { displayName: data.display_name, temporaryPassword: data.temporary_password },
      });
    } catch (error) {
      set({
        mutatingId: null,
        error: extractErrorMessage(error, "Couldn't reset this password. Please try again."),
      });
    }
  },

  dismissCredentials: () => set({ lastCredentials: null }),
}));
