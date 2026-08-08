import keycloak from "@/lib/keycloak.ts";

export async function fetchResidents() {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL}/residents`,
      {
          headers: {
              Authorization: `Bearer ${keycloak.token}`,
            },
      }
      );

  if (!response.ok) {
    throw new Error("Failed to fetch residents");
  }

  return response.json();
}

