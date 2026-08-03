import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AuthUser } from "@/types";
import keycloak from "@/lib/keycloak.ts";

interface AuthState {
  isAuthenticated: boolean;
  user: AuthUser | null;
  isLoading: boolean;
}

/**
 * Stub auth for the design pass -- accepts any non-empty credentials and signs in
 * as a fixed demo user. Replaced by real Keycloak OIDC (see
 * governance/decision-log.md) once the design is settled; the shape of this store
 * (isAuthenticated / user / login / logout) is deliberately what a Keycloak-backed
 * version will look like too, so pages built against it don't need to change.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      user: null,
      isLoading: false,
    }),
    { name: "carelens-auth" },
  ),
);
