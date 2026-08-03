import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "@/App";
import "@/index.css";
import keycloak from "@/lib/keycloak.ts";
import {useAuthStore} from "@/store/authStore.ts";

async function bootstrap() {
    await keycloak.init({
        onLoad: "login-required",
        pkceMethod: "S256",
        checkLoginIframe: false,
    });

    console.log(keycloak.token)
    await useAuthStore
    .getState()
    .loadCurrentUser();

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

