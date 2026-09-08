import axios from "axios";
import keycloak from "./keycloak";

const api = axios.create({
    baseURL: "http://localhost:8000/",
});

api.interceptors.request.use(async (config) => {
    if (keycloak.authenticated) {
        try {
            // Refreshes only if the token expires within 30s of now; a no-op otherwise.
            // Without this the token was only ever set once at login and every request
            // after it expired 401'd with no recovery path.
            await keycloak.updateToken(30);
        } catch {
            // Refresh token also expired -- proceed with whatever token is left (or
            // none). The resulting 401 is a retryable case for the offline queue
            // rather than a silent dead end.
        }
        if (keycloak.token) {
            config.headers.Authorization = `Bearer ${keycloak.token}`;
        }
    }

    return config;
});

export default api;