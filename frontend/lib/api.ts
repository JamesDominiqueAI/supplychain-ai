const CONFIGURED_API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
const DEFAULT_API_HOST = process.env.NEXT_PUBLIC_API_HOST || "127.0.0.1";
const DEFAULT_API_PORTS = [
  process.env.NEXT_PUBLIC_API_PORT,
  "8010",
  "8011",
  "8012",
].filter((value, index, values): value is string => Boolean(value) && values.indexOf(value) === index);
const REQUEST_TIMEOUT_MS = 1500;

let resolvedApiUrlPromise: Promise<string> | null = null;

function withTimeoutSignal(timeoutMs: number): AbortSignal {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), timeoutMs);
  return controller.signal;
}

async function isHealthyApi(url: string): Promise<boolean> {
  try {
    const response = await fetch(`${url}/health`, {
      signal: withTimeoutSignal(REQUEST_TIMEOUT_MS),
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function discoverApiUrl(): Promise<string> {
  if (CONFIGURED_API_URL) {
    return CONFIGURED_API_URL;
  }

  if (typeof window === "undefined") {
    return `http://${DEFAULT_API_HOST}:${DEFAULT_API_PORTS[0]}`;
  }

  const hostCandidates = Array.from(
    new Set([window.location.hostname, DEFAULT_API_HOST].filter(Boolean)),
  );

  for (const host of hostCandidates) {
    for (const port of DEFAULT_API_PORTS) {
      const candidateUrl = `http://${host}:${port}`;
      if (await isHealthyApi(candidateUrl)) {
        return candidateUrl;
      }
    }
  }

  return `http://${DEFAULT_API_HOST}:${DEFAULT_API_PORTS[0]}`;
}

export async function resolveApiUrl(): Promise<string> {
  if (!resolvedApiUrlPromise) {
    resolvedApiUrlPromise = discoverApiUrl();
  }

  return resolvedApiUrlPromise;
}

export function getFallbackApiDocsUrl(): string {
  const apiUrl = CONFIGURED_API_URL || `http://${DEFAULT_API_HOST}:${DEFAULT_API_PORTS[0]}`;
  return `${apiUrl}/docs`;
}

export function getApiDocsUrl(apiUrl: string): string {
  return `${apiUrl.replace(/\/$/, "")}/docs`;
}
