import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "@/App";
import "@/index.css";
import keycloak from "@/lib/keycloak";
import { useAuthStore } from "@/store/authStore";

function renderApp() {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  );
}

/** Shown when Keycloak successfully authenticates someone with no matching CareLens
 * `users` row -- expected for a Keycloak account that hasn't gone through a manager's
 * Staff -> Add Staff flow yet (app/modules/identity/service.py's create_staff_member
 * is what creates that row; see governance/decision-log.md's 2026-08-03 entry for why
 * login itself deliberately never does). Without this, loadCurrentUser()'s 401
 * propagated out of bootstrap() uncaught and the page just stayed blank.
 * Rendered standalone (no Router/App) since bootstrap() never got that far. */
function renderNotProvisioned() {
  const email = keycloak.tokenParsed?.email as string | undefined;
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <div className="flex min-h-screen items-center justify-center bg-brand-900 px-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-xl">
          <h1 className="text-lg font-semibold text-slate-900">No CareLens account yet</h1>
          <p className="mt-2 text-sm text-slate-500">
            {email ? (
              <>
                <span className="font-medium text-slate-700">{email}</span> is signed in, but
              </>
            ) : (
              "You're signed in, but"
            )}{" "}
            there's no CareLens staff record linked to this identity yet. Ask a manager to add you under Staff → Add
            Staff, then sign in again.
          </p>
          <button
            onClick={() => void keycloak.logout({ redirectUri: window.location.origin })}
            className="mt-6 w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700"
          >
            Sign out
          </button>
        </div>
      </div>
    </StrictMode>,
  );
}

async function bootstrap() {
  await keycloak.init({
    onLoad: "login-required",
    pkceMethod: "S256",
    checkLoginIframe: false,
  });

  try {
    await useAuthStore.getState().loadCurrentUser();
  } catch {
    renderNotProvisioned();
    return;
  }

  renderApp();
}

bootstrap();
