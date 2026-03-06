# services/bot-manager/app/orchestrators/kubernetes.py

import asyncio
import base64
import hmac
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from kubernetes import client, config
from kubernetes.client import ApiException

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mint_meeting_token(
    meeting_id: int,
    user_id: int,
    platform: str,
    native_meeting_id: str,
    ttl_seconds: int = 3600,
) -> str:
    secret = os.environ.get("ADMIN_TOKEN")
    if not secret:
        raise RuntimeError("ADMIN_TOKEN not configured; cannot mint MeetingToken")

    now = int(datetime.utcnow().timestamp())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "meeting_id": meeting_id,
        "user_id": user_id,
        "platform": platform,
        "native_meeting_id": native_meeting_id,
        "scope": "transcribe:write",
        "iss": "bot-manager",
        "aud": "transcription-collector",
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, digestmod="sha256").digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


_core_v1: Optional[client.CoreV1Api] = None


def _get_core_v1() -> client.CoreV1Api:
    global _core_v1
    if _core_v1 is None:
        config.load_incluster_config()
        _core_v1 = client.CoreV1Api()
    return _core_v1


def _namespace() -> str:
    # Prefer explicit BOT_NAMESPACE; fall back to the Pod namespace; then default.
    return (
            os.environ.get("BOT_NAMESPACE")
            or os.environ.get("POD_NAMESPACE")
            or "default"
    )


def _bot_image() -> str:
    return os.environ.get("BOT_IMAGE_NAME", "vexa-bot:dev")


def _bot_sa_name() -> Optional[str]:
    # Optional: attach a ServiceAccount to bot pods (usually not required).
    v = os.environ.get("BOT_SERVICE_ACCOUNT_NAME", "").strip()
    return v or None


def _bot_resources() -> Optional[client.V1ResourceRequirements]:
    cpu_request = os.environ.get("BOT_POD_CPU_REQUEST", "500m").strip()
    cpu_limit = os.environ.get("BOT_POD_CPU_LIMIT", "2000m").strip()
    mem_request = os.environ.get("BOT_POD_MEMORY_REQUEST", "512Mi").strip()
    mem_limit = os.environ.get("BOT_POD_MEMORY_LIMIT", "4Gi").strip()

    return client.V1ResourceRequirements(
        requests={"cpu": cpu_request, "memory": mem_request},
        limits={"cpu": cpu_limit, "memory": mem_limit},
    )


def _bot_manager_callback_url() -> Optional[str]:
    # Optional in BotConfig, but useful for lifecycle callbacks.
    # In k8s: point to bot-manager service DNS.
    return os.environ.get("BOT_MANAGER_CALLBACK_URL")  # e.g. http://vexa-bot-manager:8080/bots/internal/callback/exited


def _default_automatic_leave() -> Dict[str, int]:
    # Defaults documented for bot automatic leave timeouts (ms)
    return {
        "waitingRoomTimeout": int(os.environ.get("BOT_WAITING_ROOM_TIMEOUT_MS", "300000")),
        "noOneJoinedTimeout": int(os.environ.get("BOT_NO_ONE_JOINED_TIMEOUT_MS", "120000")),
        "everyoneLeftTimeout": int(os.environ.get("BOT_EVERYONE_LEFT_TIMEOUT_MS", "60000")),
    }

def _teams_speaker_tuning() -> Dict[str, int]:
    return {
        "signalLossGraceMs": int(os.environ.get("TEAMS_SIGNAL_LOSS_GRACE_MS", "2000")),
        "speakingKeepaliveMs": int(os.environ.get("TEAMS_SPEAKING_KEEPALIVE_MS", "8000")),
    }


def _build_bot_pod(
    user_id: int,
    meeting_id: int,
    meeting_url: str,
    platform: str,
    bot_name: Optional[str],
    user_token: str,
    native_meeting_id: str,
    language: Optional[str],
    task: Optional[str],
    transcription_tier: Optional[str],
    recording_enabled: Optional[bool],
    transcribe_enabled: Optional[bool],
    zoom_obf_token: Optional[str],
    voice_agent_enabled: Optional[bool],
    default_avatar_url: Optional[str],
) -> Tuple[str, str]:
    connection_id = str(uuid.uuid4())
    pod_name = f"vexa-bot-{meeting_id}-{connection_id[:8]}"

    redis_url = os.environ.get("REDIS_URL")
    whisper_url = os.environ.get("WHISPER_LIVE_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL is required in bot-manager env")
    if not whisper_url:
        raise RuntimeError("WHISPER_LIVE_URL is required in bot-manager env")

    meeting_token = _mint_meeting_token(
        meeting_id=meeting_id,
        user_id=user_id,
        platform=platform,
        native_meeting_id=native_meeting_id,
    )

    bot_config: Dict[str, Any] = {
        "platform": platform,
        "meetingUrl": meeting_url,
        "botName": bot_name or f"VexaBot-{uuid.uuid4().hex[:6]}",
        "token": meeting_token,
        "connectionId": connection_id,
        "nativeMeetingId": native_meeting_id,
        "meeting_id": meeting_id,
        "redisUrl": redis_url,
        "language": language,
        "task": task,
        "transcriptionTier": transcription_tier or "realtime",
        "transcribeEnabled": True if transcribe_enabled is None else bool(transcribe_enabled),
        "obfToken": zoom_obf_token if platform == "zoom" else None,
        "container_name": pod_name,
        "automaticLeave": _default_automatic_leave(),
        "teamsSpeaker": _teams_speaker_tuning(),
    }
    if recording_enabled is not None:
        bot_config["recordingEnabled"] = bool(recording_enabled)
    if voice_agent_enabled is not None:
        bot_config["voiceAgentEnabled"] = bool(voice_agent_enabled)
    if default_avatar_url:
        bot_config["defaultAvatarUrl"] = default_avatar_url

    cb = _bot_manager_callback_url()
    if cb:
        bot_config["botManagerCallbackUrl"] = cb

    # Keep parity with other orchestrators: do not pass null-valued keys.
    cleaned_config = {k: v for k, v in bot_config.items() if v is not None}

    bot_env = [
        client.V1EnvVar(name="BOT_CONFIG", value=json.dumps(cleaned_config)),
        client.V1EnvVar(name="WHISPER_LIVE_URL", value=whisper_url),
        client.V1EnvVar(name="LOG_LEVEL", value=os.environ.get("BOT_LOG_LEVEL", "INFO")),
    ]

    resources = _bot_resources()

    container = client.V1Container(
        name="bot",
        image=_bot_image(),
        image_pull_policy=os.environ.get("BOT_IMAGE_PULL_POLICY", "IfNotPresent"),
        env=bot_env,
        resources=resources,
        volume_mounts=[client.V1VolumeMount(name="dshm", mount_path="/dev/shm")],
    )

    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        termination_grace_period_seconds=10,
        containers=[container],
        volumes=[
            client.V1Volume(
                name="dshm",
                empty_dir=client.V1EmptyDirVolumeSource(medium="Memory"),
            )
        ],
    )

    sa = _bot_sa_name()
    if sa:
        pod_spec.service_account_name = sa

    pod = client.V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=client.V1ObjectMeta(
            name=pod_name,
            labels={
                "app.kubernetes.io/name": "vexa",
                "app.kubernetes.io/component": "vexa-bot",
                "vexa.user_id": str(user_id),
                "vexa.meeting_id": str(meeting_id),
            },
        ),
        spec=pod_spec,
    )

    return pod, connection_id


async def start_bot_container(
    user_id: int,
    meeting_id: int,
    meeting_url: Optional[str],
    platform: str,
    bot_name: Optional[str],
    user_token: str,
    native_meeting_id: str,
    language: Optional[str],
    task: Optional[str],
    transcription_tier: Optional[str] = "realtime",
    recording_enabled: Optional[bool] = None,
    transcribe_enabled: Optional[bool] = None,
    zoom_obf_token: Optional[str] = None,
    voice_agent_enabled: Optional[bool] = None,
    default_avatar_url: Optional[str] = None,
) -> Tuple[str, str]:
    core = _get_core_v1()
    pod, connection_id = _build_bot_pod(
        user_id,
        meeting_id,
        meeting_url,
        platform,
        bot_name,
        user_token,
        native_meeting_id,
        language,
        task,
        transcription_tier,
        recording_enabled,
        transcribe_enabled,
        zoom_obf_token,
        voice_agent_enabled,
        default_avatar_url,
    )
    await asyncio.to_thread(core.create_namespaced_pod, namespace=_namespace(), body=pod)
    return pod.metadata.name, connection_id


def stop_bot_container(container_id: str) -> bool:
    core = _get_core_v1()
    grace_seconds = int(os.environ.get("BOT_POD_DELETE_GRACE_SECONDS", "0"))
    propagation_policy = os.environ.get("BOT_POD_DELETE_PROPAGATION", "Background")
    body = client.V1DeleteOptions(
        grace_period_seconds=grace_seconds,
        propagation_policy=propagation_policy,
    )
    try:
        core.delete_namespaced_pod(name=container_id, namespace=_namespace(), body=body)
        return True
    except ApiException as exc:
        if exc.status == 404:
            return True
        raise


# Import shared session recorder so main.py can create MeetingSession records.
from app.orchestrator_utils import _record_session_start  # noqa: E402


def verify_container_running(container_id: str) -> bool:
    core = _get_core_v1()
    try:
        pod = core.read_namespaced_pod(name=container_id, namespace=_namespace())
    except ApiException as exc:
        if exc.status == 404:
            return False
        raise
    phase = pod.status.phase or ""
    return phase in ("Pending", "Running")


def get_running_bots_status(user_id: int) -> List[Dict[str, Any]]:
    core = _get_core_v1()
    label_selector = f"vexa.user_id={user_id},app.kubernetes.io/component=vexa-bot"
    pods = core.list_namespaced_pod(namespace=_namespace(), label_selector=label_selector)
    out: List[Dict[str, Any]] = []
    for pod in pods.items:
        out.append(
            {
                "container_id": pod.metadata.name,
                "status": pod.status.phase,
                "start_time": pod.status.start_time,
                "labels": pod.metadata.labels or {},
            }
        )
    return out


# Optional no-op compatibility hooks (docker orchestrator has these)
def get_socket_session():
    return None


def close_docker_client():
    return None


# Session recording hook (shared with other orchestrators)
