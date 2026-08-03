import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "@/App";
import "@/index.css";
import keycloak from "@/lib/keycloak.ts";

async function bootstrap() {
    await keycloak.init({
        onLoad: "login-required",
        pkceMethod: "S256",
        checkLoginIframe: false,
    });
    
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

