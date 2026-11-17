let pendingRefresh = null;

export async function refreshAccessToken(client) {
  if (!client) return null;
  if (!pendingRefresh) {
    pendingRefresh = Promise.resolve().then(() => client.auth.refreshSession())
      .then(({ data, error }) => {
        if (error) throw error;
        return data?.session?.access_token || null;
      }).finally(() => { pendingRefresh = null; });
  }
  return pendingRefresh;
}

export async function fetchWithSessionRecovery(send, { enabled, refresh, setToken }) {
  const response = await send();
  if (response.status !== 401 || !enabled) return response;
  const token = await refresh();
  if (!token) return response;
  setToken(token);
  return send();
}
