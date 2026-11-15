"use client";

import { createClient } from "@supabase/supabase-js";

let client = null;

export function configureSupabase({ url, anonKey }) {
  const projectUrl = url || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publicKey = anonKey || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!projectUrl || !publicKey) return null;
  if (!client) {
    client = createClient(projectUrl, publicKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return client;
}

export function getSupabaseClient() {
  return client;
}
