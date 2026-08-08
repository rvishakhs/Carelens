import axios from "axios";
import keycloak from "./keycloak";

const api = axios.create({
    baseURL: "http://localhost:8000/",
});

api.interceptors.request.use(async (config) => {
    if (keycloak.authenticated && keycloak.token) {
        config.headers.Authorization = `Bearer ${keycloak.token}`;
    }

    return config;
});

export default api;