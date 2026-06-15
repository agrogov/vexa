interface ResolveBrowserApiUrlOptions {
  internalApiUrl: string;
  configuredPublicApiUrl?: string;
  requestHost: string;
  requestProto: "http" | "https";
  gatewayHostPort?: string;
}

interface BrowserApiUrlResult {
  apiUrl: string;
  publicApiUrl: string;
}

function trimTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

function hostWithoutPort(host: string): string {
  if (host.startsWith("[")) {
    const closingBracket = host.indexOf("]");
    return closingBracket === -1 ? host : host.slice(0, closingBracket + 1);
  }
  return host.split(":")[0] || host;
}

export function resolveBrowserApiUrl({
  internalApiUrl,
  configuredPublicApiUrl,
  requestHost,
  requestProto,
  gatewayHostPort,
}: ResolveBrowserApiUrlOptions): BrowserApiUrlResult {
  const publicApiUrl = configuredPublicApiUrl?.trim()
    ? trimTrailingSlash(configuredPublicApiUrl.trim())
    : "";

  if (publicApiUrl) {
    return { apiUrl: publicApiUrl, publicApiUrl };
  }

  if (gatewayHostPort?.trim()) {
    const derivedPublicApiUrl = `${requestProto}://${hostWithoutPort(requestHost)}:${gatewayHostPort.trim()}`;
    return { apiUrl: derivedPublicApiUrl, publicApiUrl: derivedPublicApiUrl };
  }

  const apiUrl = trimTrailingSlash(internalApiUrl.trim());
  return { apiUrl, publicApiUrl: "" };
}
