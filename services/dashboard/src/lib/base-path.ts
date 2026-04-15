// Base path support for sub-path deployments (e.g. /vexa on a shared domain)
const rawBasePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
const normalizedBasePath = rawBasePath.replace(/\/$/, "");

export const basePath = normalizedBasePath;

export function withBasePath(path: string): string {
  if (!normalizedBasePath) {
    return path;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (normalizedPath === "/") {
    return normalizedBasePath || "/";
  }
  return `${normalizedBasePath}${normalizedPath}`;
}

/**
 * Build a noVNC-compatible websockify path= parameter that includes the base
 * path prefix so the WebSocket URL is routed correctly behind a sub-path proxy.
 * e.g. basePath="/vexa2", token="123" → "vexa2/b/123/vnc/websockify"
 */
export function vncWsPath(token: string | number): string {
  const prefix = normalizedBasePath.replace(/^\//, ""); // strip leading slash
  return prefix ? `${prefix}/b/${token}/vnc/websockify` : `b/${token}/vnc/websockify`;
}

export function stripBasePath(path: string): string {
  if (!normalizedBasePath || !path.startsWith(normalizedBasePath)) {
    return path;
  }
  const stripped = path.slice(normalizedBasePath.length);
  return stripped === "" ? "/" : stripped;
}
