// Refresh a Discord-CDN deck screenshot URL on demand and persist the new value.
//
// Frontend calls this when the stored deck_screenshot_url's `ex` (expiration) param has passed
// or is within ~1h of passing. Function calls Discord's POST /attachments/refresh-urls, writes
// the refreshed URL back to pod_draft_participants, and returns it. On any failure the function
// returns the existing URL so callers degrade gracefully.
//
// Stack: Deno runtime, Supabase Edge Functions.
// Secrets required: SUPABASE_URL (built-in), SUPABASE_SERVICE_ROLE_KEY (built-in), DISCORD_BOT_TOKEN.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.0";

declare const EdgeRuntime: { waitUntil(promise: Promise<unknown>): void };

const FRESH_WINDOW_MS = 60 * 60 * 1000;
const DISCORD_REFRESH_ENDPOINT = "https://discord.com/api/v10/attachments/refresh-urls";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, apikey, x-client-info",
};

interface RequestBody {
  eventId?: string;
  displayName?: string;
}

interface RefreshResponse {
  url: string | null;
  refreshed: boolean;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }
  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  let body: RequestBody;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  const eventId = body.eventId?.trim();
  const displayName = body.displayName?.trim();
  if (!eventId || !displayName) {
    return json({ error: "eventId and displayName are required" }, 400);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SERVICE_ROLE_JWT") ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const botToken = Deno.env.get("DISCORD_BOT_TOKEN");
  if (!supabaseUrl || !serviceRoleKey || !botToken) {
    console.error("missing required env vars");
    return json({ error: "Server misconfigured" }, 500);
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
    global: { headers: { Authorization: `Bearer ${serviceRoleKey}` } },
  });

  const { data, error } = await supabase
    .from("pod_draft_participants")
    .select("id, deck_screenshot_url")
    .eq("event_id", eventId)
    .eq("display_name", displayName)
    .maybeSingle();

  if (error) {
    console.error(`participant lookup failed: ${error.message}`);
    return json({ error: "Lookup failed" }, 500);
  }
  if (!data || !data.deck_screenshot_url) {
    return json({ url: null, refreshed: false } satisfies RefreshResponse, 200);
  }

  const currentUrl = data.deck_screenshot_url as string;

  if (!isDiscordCdnUrl(currentUrl)) {
    return json({ url: currentUrl, refreshed: false } satisfies RefreshResponse, 200);
  }

  const expiryMs = parseDiscordExpiryMs(currentUrl);
  if (expiryMs !== null && expiryMs - Date.now() > FRESH_WINDOW_MS) {
    return json({ url: currentUrl, refreshed: false } satisfies RefreshResponse, 200);
  }

  const refreshed = await refreshViaDiscord(currentUrl, botToken);
  if (!refreshed) {
    return json({ url: currentUrl, refreshed: false } satisfies RefreshResponse, 200);
  }

  const writeback = supabase
    .from("pod_draft_participants")
    .update({ deck_screenshot_url: refreshed })
    .eq("id", data.id)
    .then(({ error: updateError }) => {
      if (updateError) console.warn(`writeback failed: ${updateError.message}`);
    });
  EdgeRuntime.waitUntil(writeback);

  return json({ url: refreshed, refreshed: true } satisfies RefreshResponse, 200);
});

function isDiscordCdnUrl(url: string): boolean {
  return url.includes("cdn.discordapp.com") || url.includes("media.discordapp.net");
}

function parseDiscordExpiryMs(url: string): number | null {
  try {
    const ex = new URL(url).searchParams.get("ex");
    if (!ex) return null;
    const seconds = parseInt(ex, 16);
    return Number.isFinite(seconds) ? seconds * 1000 : null;
  } catch {
    return null;
  }
}

async function refreshViaDiscord(url: string, botToken: string): Promise<string | null> {
  try {
    const resp = await fetch(DISCORD_REFRESH_ENDPOINT, {
      method: "POST",
      headers: {
        "Authorization": `Bot ${botToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ attachment_urls: [url] }),
    });
    if (!resp.ok) {
      console.warn(`Discord refresh returned ${resp.status}`);
      return null;
    }
    const data = await resp.json();
    const item = data?.refreshed_urls?.[0];
    return typeof item?.refreshed === "string" ? item.refreshed : null;
  } catch (err) {
    console.warn(`Discord refresh threw: ${err}`);
    return null;
  }
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}
