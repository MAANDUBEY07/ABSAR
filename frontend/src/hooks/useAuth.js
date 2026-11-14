/**
 * useAuth Hook
 * Custom React hook for accessing current authenticated candidate session.
 */

export function useAuth() {
  return { user: null, loading: false };
}
