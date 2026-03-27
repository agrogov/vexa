# Fix GPU inference in transcription-service (libcublas.so.12 not found)

## PR Title
`fix(transcription-service): resolve libcublas.so.12 not found on GPU VM deployment`

## PR Description

### Problem

When deploying `transcription-service` on a GPU VM using the `nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04` base image, the service failed to load the Whisper model with:

```
Library libcublas.so.12 is not found or cannot be loaded
```

`ctranslate2` 4.7.x does **not** bundle CUDA shared libraries — it ships only `_ext.cpython-310-x86_64-linux-gnu.so` and relies on finding `libcublas.so.12`, `libcublasLt.so.12`, and `libcudart.so.12` at runtime via `dlopen`. The `nvidia/cuda:runtime` base image does not include cuBLAS dev/static libs, and `LD_LIBRARY_PATH` / `ldconfig` approaches proved unreliable across Docker layer boundaries.

### Root Cause

`ctranslate2` calls `dlopen("libcublas.so.12")` lazily at GPU inference time. If the library is not in the dynamic linker search path **at that exact moment**, inference fails — even if the `.so` files are present on disk at a non-standard path.

### Fix

Two complementary approaches applied together:

1. **`requirements.txt` — add CUDA pip packages**
   Added `nvidia-cublas-cu12` and `nvidia-cuda-runtime-cu12`. These pip packages install `libcublas.so.12`, `libcublasLt.so.12`, and `libcudart.so.12` under `/usr/local/lib/python3.10/site-packages/nvidia/*/lib/`.

2. **`Dockerfile` — symlink pip CUDA libs into `/usr/local/lib`**
   After pip install, symlinks all `*.so*` files from the nvidia pip lib dirs into `/usr/local/lib/` (always in the linker search path) and runs `ldconfig`. This is a belt-and-suspenders fallback for any path that resolves via the OS linker.

3. **`main.py` — `_preload_cuda_libs()` with `RTLD_GLOBAL`**
   At startup, before `WhisperModel()` is created, explicitly `ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)` loads `libcudart.so.12`, `libcublasLt.so.12`, and `libcublas.so.12` in dependency order. `RTLD_GLOBAL` exports symbols to the global namespace so that `ctranslate2`'s subsequent lazy `dlopen` calls find them. This is the primary fix — the symlink approach is defense-in-depth.

4. **`main.py` — `_log_cuda_diagnostics()` at startup**
   Logs Python/library versions, `nvidia-smi` output, ctranslate2 package contents, nvidia pip lib dirs, and explicit `.so` file locations. Essential for debugging GPU VM deployments without direct SSH/container access.

### Additional Changes

- **`MAX_CONCURRENT_TRANSCRIPTIONS` default: 2 → 20**
  CTranslate2 serializes CUDA ops internally; concurrent requests queue on the GPU rather than blocking. RTX 4090 handles 20 concurrent requests with ~3s worst-case latency. Raise default to avoid artificial throughput bottleneck.

- **`nginx.conf` rate limits raised** (sync with upstream commit `781c91ab`):
  - `rate`: 10r/s → 100r/s
  - `burst`: 20 → 100
  - `limit_conn per IP`: 5 → 50

## Files Changed

| File | Change |
|------|--------|
| `services/transcription-service/requirements.txt` | Add `nvidia-cublas-cu12`, `nvidia-cuda-runtime-cu12` |
| `services/transcription-service/Dockerfile` | Symlink nvidia pip libs → `/usr/local/lib` + `ldconfig` |
| `services/transcription-service/main.py` | `_preload_cuda_libs()` + `_log_cuda_diagnostics()` + concurrency default 2→20 |
| `services/transcription-service/nginx.conf` | Rate/conn limits: 10→100r/s, burst 20→100, conn 5→50 |

## Deployment Notes

- Rebuild the image with `--no-cache` to ensure the pip install and symlink steps run fresh.
- Pass `-e VAD_FILTER=false` when running on a GPU VM behind WhisperLive — WhisperLive already applies VAD before sending audio chunks, so double-filtering removes all audio.
- Pass `-e API_TOKEN=<token>` to require authentication.
