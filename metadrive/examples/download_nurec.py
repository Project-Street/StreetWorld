#!/usr/bin/env python3
"""Download and extract NuRec .usdz files under a relative HF dataset path."""

import argparse
import multiprocessing as mp
import os
import queue
import re
import threading
import time
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download, login

RETRYABLE_DOWNLOAD_ERROR_TYPES = {
    "ChunkedEncodingError",
    "ConnectTimeout",
    "ConnectionError",
    "LocalEntryNotFoundError",
    "ProxyError",
    "ReadTimeout",
    "Timeout",
    "TimeoutError",
}

DELETE_AFTER_EXTRACT = (
    "sequence_tracks.usda",
    "mesh.usd",
    "volume.nurec",
    "volume.usda",
    "mesh.ply",
    "mesh_ground.usd",
    "checkpoint.ckpt",
)


@dataclass(frozen=True)
class PipelineItem:
    index: int
    total: int
    relpath: str
    batch_name: str
    dest_path: Path


def normalize_path(path: str) -> str:
    return path.strip().strip("/")


def batch_name_from_relpath(relpath: str) -> str:
    m = re.search(r"(Batch\d+)", relpath)
    return m.group(1) if m else "Batch_unknown"


def collect_usdz_files(files: list[str], target_path: str) -> list[str]:
    if target_path.endswith(".usdz"):
        return [target_path] if target_path in files else []
    prefix = f"{target_path}/"
    return [p for p in files if p.startswith(prefix) and p.endswith(".usdz")]


def download_cache_dir(local_dir: Path, relpath: str) -> Path:
    return local_dir / ".cache" / "huggingface" / "download" / Path(relpath).parent


def download_progress_snapshot(cache_dir: Path) -> tuple[int, int] | None:
    stats = []
    for path in cache_dir.glob("*.incomplete"):
        if not path.exists():
            continue
        stat = path.stat()
        stats.append((stat.st_size, stat.st_mtime_ns))

    if not stats:
        return None

    total_size = sum(size for size, _ in stats)
    latest_mtime_ns = max(mtime_ns for _, mtime_ns in stats)
    return total_size, latest_mtime_ns


def cleanup_download_artifacts(local_dir: Path, relpath: str) -> None:
    cache_dir = download_cache_dir(local_dir, relpath)
    if cache_dir.exists():
        for path in cache_dir.glob("*.incomplete"):
            path.unlink(missing_ok=True)
        for path in cache_dir.glob("*.lock"):
            path.unlink(missing_ok=True)

    downloaded_path = local_dir / relpath
    downloaded_path.unlink(missing_ok=True)


def has_stale_download_artifacts(
    *,
    local_dir: Path,
    relpath: str,
    stalled_timeout_seconds: float,
) -> bool:
    snapshot = download_progress_snapshot(download_cache_dir(local_dir, relpath))
    if snapshot is None:
        return False

    _, latest_mtime_ns = snapshot
    stalled_for_ns = time.time_ns() - latest_mtime_ns
    return stalled_for_ns >= int(stalled_timeout_seconds * 1_000_000_000)


def _download_file_process(
    *,
    result_queue: mp.Queue,
    repo_id: str,
    revision: str | None,
    relpath: str,
    local_dir: str,
    hf_api_token: str | None,
) -> None:
    try:
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=revision,
            filename=relpath,
            local_dir=local_dir,
            token=hf_api_token,
        )
    except BaseException as exc:
        result_queue.put(
            {
                "ok": False,
                "error": traceback.format_exc(),
                "exc_type": type(exc).__name__,
                "exc_module": type(exc).__module__,
            }
        )
        return

    result_queue.put({"ok": True, "downloaded_path": downloaded_path})


def terminate_download_process(process: mp.Process) -> None:
    if not process.is_alive():
        process.join()
        return

    process.terminate()
    process.join(timeout=10)
    if process.is_alive():
        process.kill()
        process.join()


def is_retryable_download_error(result: dict[str, object] | None) -> bool:
    if not result or result.get("ok") is not False:
        return False

    exc_type = result.get("exc_type")
    return isinstance(exc_type, str) and exc_type in RETRYABLE_DOWNLOAD_ERROR_TYPES


def download_with_stall_restart(
    *,
    item: PipelineItem,
    stop_event: threading.Event,
    repo_id: str,
    revision: str | None,
    local_dir: Path,
    hf_api_token: str | None,
    stalled_timeout_seconds: float,
    max_stalled_retries: int,
    progress_poll_seconds: float = 5.0,
) -> Path:
    ctx = mp.get_context("spawn")
    cache_dir = download_cache_dir(local_dir, item.relpath)
    attempts = 0
    retry_limit = None if max_stalled_retries <= 0 else max_stalled_retries

    while True:
        if stop_event.is_set():
            raise RuntimeError(f"Stop requested while downloading {item.relpath}")

        attempts += 1
        if attempts > 1 or has_stale_download_artifacts(
            local_dir=local_dir,
            relpath=item.relpath,
            stalled_timeout_seconds=stalled_timeout_seconds,
        ):
            cleanup_download_artifacts(local_dir, item.relpath)

        result_queue: mp.Queue = ctx.Queue()
        process = ctx.Process(
            target=_download_file_process,
            kwargs=dict(
                result_queue=result_queue,
                repo_id=repo_id,
                revision=revision,
                relpath=item.relpath,
                local_dir=str(local_dir),
                hf_api_token=hf_api_token,
            ),
            name=f"download-{item.index}",
        )
        process.start()

        last_snapshot = download_progress_snapshot(cache_dir)
        last_progress_at = time.monotonic()
        result: dict[str, object] | None = None

        while True:
            if stop_event.is_set():
                terminate_download_process(process)
                result_queue.close()
                raise RuntimeError(f"Stop requested while downloading {item.relpath}")

            try:
                result = result_queue.get_nowait()
            except queue.Empty:
                result = None if result is None else result

            current_snapshot = download_progress_snapshot(cache_dir)
            if current_snapshot != last_snapshot:
                last_snapshot = current_snapshot
                last_progress_at = time.monotonic()

            if process.is_alive():
                stalled_for = time.monotonic() - last_progress_at
                if stalled_for >= stalled_timeout_seconds:
                    terminate_download_process(process)
                    cleanup_download_artifacts(local_dir, item.relpath)
                    result_queue.close()

                    if retry_limit is not None and attempts >= retry_limit:
                        raise RuntimeError(
                            f"{item.relpath} stalled for {stalled_timeout_seconds:.0f}s "
                            f"on {attempts} attempts"
                        )

                    retry_note = (
                        f"{attempts}/inf"
                        if retry_limit is None
                        else f"{attempts}/{retry_limit}"
                    )
                    print(
                        f"{item.batch_name} {item.index}/{item.total} stalled for "
                        f"{stalled_timeout_seconds:.0f}s; retrying "
                        f"({retry_note}) -> {item.relpath}"
                    )
                    break

                time.sleep(progress_poll_seconds)
                continue

            process.join()
            if result is None:
                try:
                    result = result_queue.get_nowait()
                except queue.Empty:
                    result = None
            result_queue.close()

            if process.exitcode == 0 and result and result.get("ok") is True:
                return Path(str(result["downloaded_path"]))

            if is_retryable_download_error(result):
                cleanup_download_artifacts(local_dir, item.relpath)

                if retry_limit is not None and attempts >= retry_limit:
                    raise RuntimeError(
                        f"{item.relpath} failed with retryable error after {attempts} attempts:\n"
                        f"{result['error']}"
                    )

                retry_note = (
                    f"{attempts}/inf"
                    if retry_limit is None
                    else f"{attempts}/{retry_limit}"
                )
                exc_type = result.get("exc_type", "download error")
                print(
                    f"{item.batch_name} {item.index}/{item.total} {exc_type}; retrying "
                    f"({retry_note}) -> {item.relpath}"
                )
                break

            error_message = (
                result["error"]
                if result and "error" in result
                else f"download process exited with code {process.exitcode}"
            )
            raise RuntimeError(f"Failed to download {item.relpath}:\n{error_message}")


def download_worker(
    *,
    extract_queue: queue.Queue[PipelineItem],
    stop_event: threading.Event,
    repo_id: str,
    revision: str | None,
    local_dir: Path,
    hf_api_token: str | None,
    pending_items: list[PipelineItem],
    stalled_timeout_seconds: float,
    max_stalled_retries: int,
) -> None:
    for item in pending_items:
        if stop_event.is_set():
            return
        if item.dest_path.exists():
            print(f"{item.batch_name} {item.index}/{item.total} skip-download -> {item.dest_path}")
            extract_queue.put(item)
            continue
        downloaded_path = download_with_stall_restart(
            item=item,
            stop_event=stop_event,
            repo_id=repo_id,
            revision=revision,
            local_dir=local_dir,
            hf_api_token=hf_api_token,
            stalled_timeout_seconds=stalled_timeout_seconds,
            max_stalled_retries=max_stalled_retries,
        )
        if downloaded_path.resolve() != item.dest_path.resolve():
            raise RuntimeError(f"downloaded path mismatch: {downloaded_path} != {item.dest_path}")
        extract_queue.put(item)
        print(f"{item.batch_name} {item.index}/{item.total} downloaded -> {item.dest_path}")


def safe_extract_all(zf: zipfile.ZipFile, out_dir: Path) -> None:
    out_dir_resolved = out_dir.resolve()
    for member in zf.infolist():
        member_path = out_dir / member.filename
        try:
            member_resolved = member_path.resolve()
        except FileNotFoundError:
            member_resolved = member_path.parent.resolve() / member_path.name
        if out_dir_resolved not in (member_resolved, *member_resolved.parents):
            raise ValueError(f"Unsafe archive member path: {member.filename}")
    zf.extractall(out_dir)


def extract_usdz(usdz_path: Path) -> Path:
    out_dir = usdz_path.with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(usdz_path, "r") as zf:
        safe_extract_all(zf, out_dir)
    for relpath in DELETE_AFTER_EXTRACT:
        (out_dir / relpath).unlink()
    return out_dir


def extract_worker(
    *,
    extract_queue: queue.Queue[PipelineItem],
    extract_input_done: threading.Event,
    stop_event: threading.Event,
) -> None:
    while True:
        if stop_event.is_set() and extract_queue.empty():
            return
        if extract_input_done.is_set() and extract_queue.empty():
            return
        try:
            item = extract_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        out_dir = item.dest_path.with_suffix("")
        if out_dir.exists():
            print(f"{item.batch_name} {item.index}/{item.total} skip-extract -> {out_dir}")
            extract_queue.task_done()
            continue

        out_dir = extract_usdz(item.dest_path)
        print(f"{item.batch_name} {item.index}/{item.total} extracted -> {out_dir}")
        extract_queue.task_done()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download .usdz files under a relative path from an HF dataset repo. "
            "Each file is downloaded to the destination and extracted into a "
            "same-name directory."
        )
    )
    parser.add_argument(
        "--path",
        required=True,
        help=(
            "Relative path in dataset repo root (relative to "
            "'https://huggingface.co/datasets/<repo-id>/tree/main/')."
        ),
    )
    parser.add_argument("--local-dir", required=True, help="Destination directory")
    parser.add_argument(
        "--repo-id",
        default="nvidia/PhysicalAI-Autonomous-Vehicles-NuRec",
        help="Hugging Face dataset repo id",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional dataset revision (tag/branch/commit)",
    )
    parser.add_argument(
        "--stalled-timeout-seconds",
        type=float,
        default=120.0,
        help="Restart a file download if its .incomplete cache file does not change for this many seconds.",
    )
    parser.add_argument(
        "--max-stalled-retries",
        type=int,
        default=0,
        help="Maximum retries for a stalled file. Use 0 or a negative value for unlimited retries.",
    )
    args = parser.parse_args()

    target_path = normalize_path(args.path)
    if not target_path:
        print("Invalid path.")
        return 1

    local_dir = Path(args.local_dir).expanduser().resolve()
    local_dir.mkdir(parents=True, exist_ok=True)

    hf_api_token = os.getenv("HF_TOKEN")
    if hf_api_token:
        login(token=hf_api_token)
    else:
        print("HF_TOKEN not set; attempting anonymous access.")

    api = HfApi(token=hf_api_token)
    files = api.list_repo_files(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=args.revision,
    )

    usdz_files = sorted(collect_usdz_files(files, target_path))
    if not usdz_files:
        print(f"No .usdz files found for path: {target_path}")
        return 1

    total = len(usdz_files)
    pending_items: list[PipelineItem] = []
    extract_queue: queue.Queue[PipelineItem] = queue.Queue()
    extract_input_done = threading.Event()
    stop_event = threading.Event()
    thread_errors: list[BaseException] = []
    default_excepthook = threading.excepthook

    def fail_fast_excepthook(args: threading.ExceptHookArgs) -> None:
        stop_event.set()
        extract_input_done.set()
        thread_errors.append(args.exc_value)
        default_excepthook(args)

    threading.excepthook = fail_fast_excepthook

    for i, relpath in enumerate(usdz_files, start=1):
        batch_name = batch_name_from_relpath(relpath)
        dest_file = local_dir / relpath
        pending_items.append(
            PipelineItem(
                index=i,
                total=total,
                relpath=relpath,
                batch_name=batch_name,
                dest_path=dest_file,
            )
        )

    downloader = threading.Thread(
        target=download_worker,
        kwargs=dict(
            extract_queue=extract_queue,
            stop_event=stop_event,
            repo_id=args.repo_id,
            revision=args.revision,
            local_dir=local_dir,
            hf_api_token=hf_api_token,
            pending_items=pending_items,
            stalled_timeout_seconds=args.stalled_timeout_seconds,
            max_stalled_retries=args.max_stalled_retries,
        ),
        name="nurec-downloader",
    )
    extractor = threading.Thread(
        target=extract_worker,
        kwargs=dict(
            extract_queue=extract_queue,
            extract_input_done=extract_input_done,
            stop_event=stop_event,
        ),
        name="nurec-extractor",
    )

    extractor.start()
    downloader.start()
    downloader.join()
    extract_input_done.set()
    extractor.join()

    if thread_errors:
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
