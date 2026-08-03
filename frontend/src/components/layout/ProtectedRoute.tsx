import { Outlet } from "react-router-dom";
import keycloak from "@/lib/keycloak";
import {useAuthStore} from "@/store/authStore.ts";

export function ProtectedRoute() {
const user = useAuthStore((s) => s.user);

  if (!user) {
      return <div>Loading</div>;
  }

  return <Outlet />;
  }

