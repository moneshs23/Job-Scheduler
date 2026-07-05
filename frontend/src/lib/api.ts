import axios from "axios";

const TOKEN_KEY = "djs_access_token";
const REFRESH_KEY = "djs_refresh_token";

export const tokenStorage = {
  getAccess: () => localStorage.getItem(TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshPromise: Promise<string> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry && tokenStorage.getRefresh()) {
      original._retry = true;
      try {
        refreshPromise ??= axios
          .post("/api/v1/auth/refresh", { refresh_token: tokenStorage.getRefresh() })
          .then((res) => {
            tokenStorage.set(res.data.access_token, res.data.refresh_token);
            return res.data.access_token as string;
          })
          .finally(() => {
            refreshPromise = null;
          });
        const newToken = await refreshPromise;
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch {
        tokenStorage.clear();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);
