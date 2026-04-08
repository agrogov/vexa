"use client";

import { useState, useEffect } from "react";
import { Monitor, Plus, ExternalLink, Trash2, Loader2, Save, Copy } from "lucide-react";
import { withBasePath } from "@/lib/base-path";
import { useRuntimeConfig } from "@/hooks/use-runtime-config";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface BrowserSession {
  id: number;
  status: string;
  native_meeting_id: string;
  data: {
    mode: string;
    session_token: string;
  };
  created_at: string;
}

export default function BrowserPage() {
  const { config } = useRuntimeConfig();
  const apiUrl = config?.publicApiUrl ?? config?.apiUrl ?? "http://localhost:18056";
  const [session, setSession] = useState<BrowserSession | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [vncReady, setVncReady] = useState(false);

  useEffect(() => {
    fetchActiveSession();
  }, []);

  // When session appears (created or restored), wait for VNC to be reachable
  useEffect(() => {
    if (!session) { setVncReady(false); return; }
    const token = session.data?.session_token;
    if (!token) { setVncReady(true); return; }
    const probeUrl = `${apiUrl}/b/${token}/vnc/vnc.html`;
    // If page was restored (not just created), skip the wait
    if (vncReady) return;
    waitForVnc(probeUrl);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  async function fetchActiveSession() {
    setIsLoading(true);
    try {
      const response = await fetch(withBasePath("/api/vexa/meetings"));
      if (response.ok) {
        const data = await response.json();
        const meetings = Array.isArray(data) ? data : data.meetings || [];
        const active = meetings.find((m: BrowserSession) => m.data?.mode === "browser_session" && m.status === "active");
        setSession(active || null);
        if (active) setVncReady(true); // already running, skip readiness wait
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setIsLoading(false);
    }
  }

  async function waitForVnc(url: string, maxAttempts = 20) {
    for (let i = 0; i < maxAttempts; i++) {
      try {
        const res = await fetch(url, { method: "HEAD" });
        if (res.ok) { setVncReady(true); return; }
      } catch { /* not ready yet */ }
      await new Promise(r => setTimeout(r, 1000));
    }
    // Show iframe anyway after timeout — let noVNC handle reconnect
    setVncReady(true);
  }

  async function createSession() {
    setIsCreating(true);
    setVncReady(false);
    try {
      const response = await fetch(withBasePath("/api/vexa/bots"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "browser_session" }),
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setSession(data);
      toast.success("Browser session created");
    } catch (error) {
      toast.error("Failed to create session: " + (error as Error).message);
    } finally {
      setIsCreating(false);
    }
  }

  async function saveStorage() {
    if (!session) return;
    setIsSaving(true);
    try {
      const token = session.data.session_token;
      const response = await fetch(`${apiUrl}/b/${token}/save`, { method: "POST" });
      if (!response.ok) throw new Error(await response.text());
      toast.success("Storage saved");
    } catch (error) {
      toast.error("Save failed: " + (error as Error).message);
    } finally {
      setIsSaving(false);
    }
  }

  async function stopSession() {
    if (!session) return;
    try {
      const nativeId = session.native_meeting_id;
      const res = await fetch(withBasePath(`/api/vexa/bots/browser_session/${nativeId}`), { method: "DELETE" });
      if (!res.ok) throw new Error(`${res.status}`);
      setSession(null);
      toast.success("Session stopped");
    } catch (error) {
      toast.error("Failed to stop session: " + (error as Error).message);
    }
  }

  const token = session?.data?.session_token;
  // Strip protocol+host to get just the path prefix (e.g. "/vexa/api-gateway")
  const apiPrefix = apiUrl ? new URL(apiUrl, "https://x").pathname.replace(/\/$/, "") : "";
  const vncUrl = token ? `${apiUrl}/b/${token}/vnc/vnc.html?autoconnect=true&resize=scale&reconnect=true&path=${apiPrefix.replace(/^\//, "")}/b/${token}/vnc/websockify` : null;
  const cdpUrl = token ? `${apiUrl}/b/${token}/cdp-ws` : null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-64px)] gap-4">
        <Monitor className="h-16 w-16 text-muted-foreground" />
        <h2 className="text-xl font-semibold">Remote Browser</h2>
        <p className="text-muted-foreground text-center max-w-md">
          Interactive browser with persistent storage. Authenticate accounts,
          run scripts, control via Playwright CDP.
        </p>
        <Button size="lg" onClick={createSession} disabled={isCreating}>
          {isCreating ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Plus className="h-4 w-4 mr-2" />
          )}
          Start Browser Session
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-2 border-b bg-background">
        <Monitor className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Session #{session.id}</span>
        <div className="flex-1" />
        <Button variant="outline" size="sm" onClick={saveStorage} disabled={isSaving}>
          {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
          Save
        </Button>
        <Button variant="outline" size="sm" onClick={() => {
          if (cdpUrl) { navigator.clipboard.writeText(cdpUrl); toast.success("CDP URL copied"); }
        }}>
          <Copy className="h-4 w-4 mr-1" />
          CDP
        </Button>
        <Button variant="outline" size="sm" onClick={() => { if (vncUrl) window.open(vncUrl, "_blank"); }}>
          <ExternalLink className="h-4 w-4 mr-1" />
          Fullscreen
        </Button>
        <Button variant="destructive" size="sm" onClick={stopSession}>
          <Trash2 className="h-4 w-4 mr-1" />
          Stop
        </Button>
      </div>

      {/* Browser iframe */}
      {vncUrl && !vncReady && (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span className="text-sm">Starting browser...</span>
        </div>
      )}
      {vncUrl && vncReady && (
        <iframe
          src={vncUrl}
          className="flex-1 w-full border-0"
          allow="clipboard-read; clipboard-write"
        />
      )}
    </div>
  );
}
