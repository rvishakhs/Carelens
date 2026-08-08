import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "@/App";
import "@/index.css";
import { extractErrorMessage } from "@/lib/errors";
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

/** Shown when Keycloak successfully authenticates someone but /identity/me 401s --
 * either no matching CareLens `users` row (never provisioned via a manager's Staff ->
 * Add Staff flow) or an existing one with is_active=False (deactivated). Both raise
 * UnauthenticatedError with a distinct message server-side (identity/repository.py's
 * sync_from_claims) -- `reason` is that message, so this reads correctly for either
 * case without guessing which one happened. Without this, loadCurrentUser()'s 401
 * propagated out of bootstrap() uncaught and the page just stayed blank. Rendered
 * standalone (no Router/App) since bootstrap() never got that far. */
function renderSignInBlocked(reason: string) {
  const email = keycloak.tokenParsed?.email as string | undefined;
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <div className="flex min-h-screen items-center justify-center bg-brand-900 px-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 text-center shadow-xl">
          <h1 className="text-lg font-semibold text-slate-900">Can't sign in</h1>
          <p className="mt-2 text-sm text-slate-500">
            {email && (
              <>
                <span className="font-medium text-slate-700">{email}</span> —{" "}
              </>
            )}
            {reason}
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
  } catch (error) {
    renderSignInBlocked(
      extractErrorMessage(
        error,
        "There's no CareLens staff record linked to this identity yet. Ask a manager to add you under Staff → Add Staff.",
      ),
    );
    return;
  }

  renderApp();
}

bootstrap();
