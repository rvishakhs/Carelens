import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "@/App";
import "@/index.css";
import keycloak from "@/lib/keycloak.ts";

async function bootstrap() {
    const authenticated = await keycloak.init({
        onLoad: "check-sso",
        pkceMethod: "S256",
    });

    if (!authenticated) {
        await keycloak.login();
        return; // Browser is redirecting
    }

    createRoot(
        document.getElementById("root")!
    ).render(
        <StrictMode>
            <BrowserRouter>
                <App />
            </BrowserRouter>
        </StrictMode>
    );
}

bootstrap();