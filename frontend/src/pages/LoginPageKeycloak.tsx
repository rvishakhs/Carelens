import {useEffect} from "react";
import keycloak from "@/lib/keycloak.ts";

export function LoginPagekeyCloak() {
  useEffect(() => {
    keycloak.login();
  }, []);

  return <div>Redirecting to login...</div>;
}