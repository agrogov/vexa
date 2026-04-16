"""Container manager — delegates lifecycle to Runtime API, keeps exec local.

Container lifecycle (create/stop/list) goes through Runtime API.
Container exec stays local:
  - process/docker mode: docker exec subprocess
  - kubernetes mode: kubectl exec via kubernetes python client
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from agent_api import config

logger = logging.getLogger("agent_api.container_manager")


@dataclass
class ContainerInfo:
    name: str
    user_id: str
    session_id: str = "default"
    workspace_name: str = "default"
    last_activity: float = field(default_factory=time.time)


class ContainerManager:
    """Manages agent containers via Runtime API + local docker exec."""

    def __init__(self, runtime_api_url: str = "", api_key: str = ""):
        self._runtime_api = runtime_api_url or config.RUNTIME_API_URL
        self._api_key = api_key or config.API_KEY
        self._containers: dict[str, ContainerInfo] = {}  # "user_id:session_id" -> info
        self._http: Optional[httpx.AsyncClient] = None
        self._admin_http: Optional[httpx.AsyncClient] = None
        self._new_container: bool = False
        self._last_user_data: dict[str, dict] = {}  # user_id -> user.data, per-user cache
        self._ensure_locks: dict[str, asyncio.Lock] = {}  # per-user lock to prevent double-spawn

    async def startup(self):
        """Initialize HTTP clients for Runtime API and Admin API, discover existing containers."""
        headers = {"X-API-Key": self._api_key} if self._api_key else {}
        self._http = httpx.AsyncClient(
            base_url=self._runtime_api, timeout=30, headers=headers,
        )
        admin_headers = {"X-Admin-API-Key": config.ADMIN_API_TOKEN} if config.ADMIN_API_TOKEN else {}
        self._admin_http = httpx.AsyncClient(
            base_url=config.ADMIN_API_URL, timeout=10, headers=admin_headers,
        )
        # Discover existing agent containers
        try:
            resp = await self._http.get("/containers", params={"profile": "agent"})
            if resp.status_code == 200:
                for c in resp.json():
                    if c.get("status") == "running":
                        uid = c.get("user_id", "")
                        key = f"{uid}:default"
                        self._containers[key] = ContainerInfo(name=c["name"], user_id=uid, session_id="default")
                        logger.info(f"Discovered container {c['name']} for user {uid}")
        except Exception as e:
            logger.warning(f"Could not discover containers from Runtime API: {e}")
        logger.info(f"Container manager started (runtime={self._runtime_api})")

    async def shutdown(self):
        """Close HTTP clients."""
        if self._http:
            await self._http.aclose()
        if self._admin_http:
            await self._admin_http.aclose()
        logger.info("Container manager shut down")

    # --- User data ---

    async def get_user_data(self, user_id: str) -> dict:
        """Fetch full user object from admin-api. Returns empty dict on failure.

        Returns the full response (includes api_tokens, data, etc).
        Admin-api expects integer user IDs. Non-numeric user_ids skip the lookup.
        Result is cached per user_id for the container's lifetime.
        """
        # Return cached if available
        if user_id in self._last_user_data:
            return self._last_user_data[user_id]

        # Admin API requires integer user ID
        try:
            int_id = int(user_id)
        except (ValueError, TypeError):
            logger.debug(f"Non-numeric user_id '{user_id}', skipping admin-api lookup")
            return {}

        try:
            resp = await self._admin_http.get(f"/admin/users/{int_id}")
            if resp.status_code == 200:
                user_obj = resp.json() or {}
                self._last_user_data[user_id] = user_obj
                return user_obj
            elif resp.status_code == 404:
                logger.debug(f"User {int_id} not found in admin-api")
            else:
                logger.warning(f"Admin-api returned {resp.status_code} for user {int_id}")
        except Exception as e:
            logger.warning(f"Failed to fetch user data for {user_id}: {e}")
        return {}

    # --- Container operations ---

    async def _is_alive(self, name: str) -> bool:
        """Check if container/pod is actually running."""
        if config.ORCHESTRATOR_BACKEND == "kubernetes":
            return await _k8s_is_alive(name)
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "--format", "{{.State.Status}}", name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0 and stdout.decode().strip() == "running"
        except Exception:
            return False

    async def ensure_container(self, user_id: str, session_id: str = "default", **create_kwargs) -> str:
        """Ensure a running agent container exists. Returns container name.

        Additional kwargs are passed to the Runtime API POST /containers body.
        """
        self._new_container = False
        key = f"{user_id}:{session_id}"

        # Per-user lock prevents race: two concurrent requests for the same user
        # would both miss the cache and spawn duplicate pods.
        if key not in self._ensure_locks:
            self._ensure_locks[key] = asyncio.Lock()
        async with self._ensure_locks[key]:
            return await self._ensure_container_locked(user_id, session_id, key, **create_kwargs)

    async def _ensure_container_locked(self, user_id: str, session_id: str, key: str, **create_kwargs) -> str:
        """Inner ensure_container body, called while holding the per-user lock."""
        # Check local cache
        info = self._containers.get(key)
        if info:
            if await self._is_alive(info.name):
                info.last_activity = time.time()
                await self._touch(info.name)
                return info.name
            self._containers.pop(key, None)
            self._last_user_data.pop(user_id, None)  # stale config for dead container

        # Create via Runtime API
        logger.info(f"Requesting container for user {user_id} session {session_id}")
        body = {"user_id": user_id, "profile": "agent", **create_kwargs}

        # Inject Claude credentials into container config
        agent_config = body.setdefault("config", {})
        agent_env = agent_config.setdefault("env", {})
        agent_mounts = agent_config.setdefault("mounts", [])

        # Pass Anthropic credentials if available
        if config.ANTHROPIC_API_KEY:
            agent_env["ANTHROPIC_API_KEY"] = config.ANTHROPIC_API_KEY
        if config.ANTHROPIC_BASE_URL:
            agent_env["ANTHROPIC_BASE_URL"] = config.ANTHROPIC_BASE_URL

        # Wire vexa CLI to the correct in-cluster services
        # VEXA_TC: transcript endpoint (meeting-api replaced transcription-collector)
        # VEXA_MEETING_API: bot manager endpoint
        agent_env["VEXA_TC"] = config.MEETING_API_URL
        agent_env["VEXA_MEETING_API"] = config.MEETING_API_URL

        # S3/MinIO credentials for workspace sync (aws s3 sync) inside container
        if config.S3_ACCESS_KEY:
            agent_env["AWS_ACCESS_KEY_ID"] = config.S3_ACCESS_KEY
            agent_env["AWS_SECRET_ACCESS_KEY"] = config.S3_SECRET_KEY
        if config.S3_ENDPOINT:
            agent_env["S3_ENDPOINT"] = config.S3_ENDPOINT
            agent_env["AWS_DEFAULT_REGION"] = "us-east-1"

        # Mount Claude OAuth credential files if paths are set
        if config.CLAUDE_CREDENTIALS_PATH:
            agent_mounts.append(
                f"{config.CLAUDE_CREDENTIALS_PATH}:/root/.claude/.credentials.json:ro"
            )
        if config.CLAUDE_JSON_PATH:
            agent_mounts.append(
                f"{config.CLAUDE_JSON_PATH}:/root/.claude.json:ro"
            )

        # Inject per-user env vars from admin-api user.data['env']
        user_obj = await self.get_user_data(user_id)
        user_env = (user_obj.get("data") or {}).get("env", {})
        if user_env and isinstance(user_env, dict):
            agent_env.update(user_env)
            logger.info(f"Injected {len(user_env)} user env vars for {user_id}")

        # Inject user's bot API token so vexa CLI can authenticate to meeting-api
        user_tokens = user_obj.get("api_tokens", [])
        bot_token = next(
            (t["token"] for t in user_tokens if "bot" in t.get("scopes", [])),
            None,
        )
        if bot_token:
            agent_env["VEXA_BOT_API_TOKEN"] = bot_token
            logger.info(f"Injected VEXA_BOT_API_TOKEN for user {user_id}")

        resp = await self._http.post("/containers", json=body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Runtime API failed: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        name = data["name"]
        self._containers[key] = ContainerInfo(name=name, user_id=user_id, session_id=session_id)
        self._new_container = True
        logger.info(f"Container {name} created for user {user_id} session {session_id}")
        return name

    async def start_agent(self, session_id: str, agent_config: dict = None,
                          callback_url: str = None) -> str:
        """Create an agent container via Runtime API. Returns container name."""
        body = {"user_id": session_id, "profile": "agent"}
        if agent_config:
            body["config"] = agent_config
        if callback_url:
            body["callback_url"] = callback_url
        resp = await self._http.post("/containers", json=body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Runtime API failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        name = data["name"]
        key = f"{session_id}:default"
        self._containers[key] = ContainerInfo(name=name, user_id=session_id)
        return name

    async def stop_agent(self, container_id: str):
        """Stop a container via Runtime API."""
        try:
            await self._http.delete(f"/containers/{container_id}")
        except Exception as e:
            logger.warning(f"Error stopping {container_id}: {e}")
        # Remove from cache if present
        for key, info in list(self._containers.items()):
            if info.name == container_id:
                self._containers.pop(key, None)
                break

    async def get_status(self, container_id: str) -> dict:
        """Get container status from Runtime API."""
        resp = await self._http.get(f"/containers/{container_id}")
        if resp.status_code == 404:
            return {"name": container_id, "status": "not_found"}
        resp.raise_for_status()
        return resp.json()

    async def stop_session_container(self, user_id: str, session_id: str = "default"):
        """Stop the container for a specific user session."""
        key = f"{user_id}:{session_id}"
        info = self._containers.get(key)
        if not info:
            return
        await self.stop_agent(info.name)

    async def _touch(self, container: str):
        """Tell Runtime API this container is actively in use."""
        try:
            await self._http.post(f"/containers/{container}/touch")
        except Exception:
            pass

    # --- Exec operations (docker or kubernetes) ---

    async def exec_stream(self, container: str, cmd: str) -> asyncio.subprocess.Process:
        """Run a shell command in the container, return subprocess for streaming."""
        await self._touch(container)
        if config.ORCHESTRATOR_BACKEND == "kubernetes":
            return await _k8s_exec_stream(container, cmd)
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", container, "bash", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=16 * 1024 * 1024,
        )
        return proc

    async def exec_simple(self, container: str, cmd: list[str]) -> Optional[str]:
        """Run a command in the container, return stdout or None."""
        if config.ORCHESTRATOR_BACKEND == "kubernetes":
            return await _k8s_exec_simple(container, cmd)
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container, *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0 and stdout.strip():
                return stdout.decode(errors="replace").strip()
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"exec_simple failed: {e}")
        return None

    async def exec_with_stdin(self, container: str, cmd: list[str],
                              stdin_data: bytes) -> Optional[str]:
        """Run a command in the container with stdin piped. Returns stdout or None."""
        if config.ORCHESTRATOR_BACKEND == "kubernetes":
            return await _k8s_exec_with_stdin(container, cmd, stdin_data)
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "-i", container, *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=stdin_data), timeout=30,
            )
            if proc.returncode == 0 and stdout.strip():
                return stdout.decode(errors="replace").strip()
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"exec_with_stdin failed: {e}")
        return None

    async def interrupt(self, user_id: str, session_id: str = "default",
                        process_pattern: str = "claude.*stream-json"):
        """Kill active agent process in user's container."""
        key = f"{user_id}:{session_id}"
        info = self._containers.get(key)
        if not info:
            return
        try:
            await self.exec_simple(info.name, [
                "sh", "-c", f"pkill -f '{process_pattern}' || true",
            ])
        except Exception as e:
            logger.warning(f"Interrupt failed for {user_id}:{session_id}: {e}")

    async def reset_session(self, user_id: str, session_id: str = "default"):
        """Kill active process and clear session state in container."""
        await self.interrupt(user_id, session_id)
        key = f"{user_id}:{session_id}"
        info = self._containers.get(key)
        if info:
            await self.exec_simple(info.name, ["rm", "-f", "/tmp/.agent-session"])

    def get_container_name(self, user_id: str, session_id: str = "default") -> Optional[str]:
        key = f"{user_id}:{session_id}"
        info = self._containers.get(key)
        return info.name if info else None


# ---------------------------------------------------------------------------
# Kubernetes exec helpers
# ---------------------------------------------------------------------------

def _get_k8s_api():
    """Load in-cluster or kubeconfig and return CoreV1Api (cached module-level)."""
    from kubernetes import client, config as k8s_config
    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()
    return client.CoreV1Api()


async def _k8s_wait_running(pod_name: str, timeout: int = 60) -> bool:
    """Wait until pod phase is Running and all containers are ready. Returns False on timeout."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            api = _get_k8s_api()
            pod = await loop.run_in_executor(
                None,
                lambda: api.read_namespaced_pod(name=pod_name, namespace=config.K8S_NAMESPACE),
            )
            phase = pod.status.phase if pod.status else None
            if phase == "Running":
                # All containers ready
                statuses = pod.status.container_statuses or []
                if statuses and all(cs.ready for cs in statuses):
                    return True
            elif phase in ("Failed", "Succeeded", "Unknown"):
                return False
        except Exception:
            pass
        await asyncio.sleep(1)
    logger.warning(f"Timed out waiting for pod {pod_name} to be Running")
    return False


async def _k8s_is_alive(pod_name: str) -> bool:
    """Return True if the pod exists and is Running or Pending (still starting)."""
    loop = asyncio.get_event_loop()
    try:
        api = _get_k8s_api()
        pod = await loop.run_in_executor(
            None,
            lambda: api.read_namespaced_pod(name=pod_name, namespace=config.K8S_NAMESPACE),
        )
        return pod.status.phase in ("Running", "Pending")
    except Exception:
        return False


async def _k8s_exec_simple(pod_name: str, cmd: list[str], timeout: int = 30) -> Optional[str]:
    """Run a command in a K8s pod, return stdout or None."""
    from kubernetes.stream import stream as k8s_stream
    loop = asyncio.get_event_loop()
    try:
        await _k8s_wait_running(pod_name)
        api = _get_k8s_api()
        resp = await loop.run_in_executor(
            None,
            lambda: k8s_stream(
                api.connect_get_namespaced_pod_exec,
                pod_name, config.K8S_NAMESPACE,
                command=cmd,
                stderr=True, stdin=False, stdout=True, tty=False,
                _preload_content=True,
            ),
        )
        output = resp.strip() if resp else ""
        return output or None
    except Exception as e:
        logger.debug(f"k8s exec_simple failed for {pod_name}: {e}")
        return None


async def _k8s_exec_with_stdin(pod_name: str, cmd: list[str],
                                stdin_data: bytes, timeout: int = 30) -> Optional[str]:
    """Run a command in a K8s pod with stdin data. Returns stdout or None."""
    from kubernetes.stream import stream as k8s_stream
    loop = asyncio.get_event_loop()
    try:
        await _k8s_wait_running(pod_name)
        api = _get_k8s_api()

        def _run():
            ws = k8s_stream(
                api.connect_get_namespaced_pod_exec,
                pod_name, config.K8S_NAMESPACE,
                command=cmd,
                stderr=True, stdin=True, stdout=True, tty=False,
                _preload_content=False,
            )
            ws.write_stdin(stdin_data.decode(errors="replace"))
            # Closing the websocket signals EOF to the remote process
            ws.close()
            return None

        resp = await asyncio.wait_for(
            loop.run_in_executor(None, _run),
            timeout=timeout + 5,
        )
        return resp.strip() if resp else None
    except Exception as e:
        logger.debug(f"k8s exec_with_stdin failed for {pod_name}: {e}")
        return None


class _K8sStreamProcess:
    """Mimics asyncio.subprocess.Process stdout interface for K8s exec streaming."""

    def __init__(self):
        self._queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.stdout = self
        self.returncode = 0

    async def __aiter__(self):
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                break
            yield chunk

    async def wait(self):
        pass


async def _k8s_exec_stream(pod_name: str, cmd: str) -> _K8sStreamProcess:
    """Start a streaming exec in a K8s pod. Returns a process-like object."""
    from kubernetes.stream import stream as k8s_stream

    proc = _K8sStreamProcess()
    loop = asyncio.get_event_loop()

    async def _stream():
        try:
            if not await _k8s_wait_running(pod_name):
                logger.error(f"Pod {pod_name} not ready for exec_stream")
                await proc._queue.put(None)
                return
            api = _get_k8s_api()
            full_cmd = ["bash", "-c", cmd]

            def _open_ws():
                return k8s_stream(
                    api.connect_get_namespaced_pod_exec,
                    pod_name, config.K8S_NAMESPACE,
                    command=full_cmd,
                    stderr=True, stdin=False, stdout=True, tty=False,
                    _preload_content=False,
                )

            ws = await loop.run_in_executor(None, _open_ws)
            try:
                while True:
                    def _read():
                        ws.update(timeout=1)
                        return ws.read_stdout()

                    data = await loop.run_in_executor(None, _read)
                    if data:
                        await proc._queue.put(data.encode() if isinstance(data, str) else data)
                    elif not ws.is_open():
                        break
            finally:
                ws.close()
        except Exception as e:
            logger.error(f"k8s exec_stream failed for {pod_name}: {e}")
        finally:
            await proc._queue.put(None)

    asyncio.create_task(_stream())
    return proc
