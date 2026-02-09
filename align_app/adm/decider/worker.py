import gc
import hashlib
import json
import logging
import os
import traceback
from dataclasses import dataclass
from typing import Dict, Tuple, Callable, Any, Optional
from multiprocessing import Queue
from align_utils.models import ADMResult
from .executor import instantiate_adm
from .types import DeciderParams


def extract_cache_key(resolved_config: Dict[str, Any]) -> str:
    cache_str = json.dumps(resolved_config, sort_keys=True)
    return hashlib.md5(cache_str.encode()).hexdigest()


@dataclass
class CacheQuery:
    resolved_config: Dict[str, Any]


@dataclass
class CacheQueryResult:
    is_cached: bool
    is_downloaded: Optional[bool]


def _extract_model_name(resolved_config: Dict[str, Any]) -> Optional[str]:
    if not isinstance(resolved_config, dict):
        return None

    if isinstance(resolved_config.get("model_name"), str):
        return resolved_config["model_name"]

    structured = resolved_config.get("structured_inference_engine")
    if isinstance(structured, dict) and isinstance(structured.get("model_name"), str):
        return structured["model_name"]

    for value in resolved_config.values():
        if isinstance(value, dict):
            found = _extract_model_name(value)
            if found:
                return found
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _extract_model_name(item)
                    if found:
                        return found
    return None


def _is_model_downloaded(model_name: Optional[str]) -> Optional[bool]:
    if not model_name:
        return None

    if os.path.exists(model_name):
        return True

    try:
        from huggingface_hub import snapshot_download
    except Exception:
        return None

    try:
        snapshot_download(model_name, local_files_only=True)
        return True
    except Exception:
        return False


def decider_worker_func(task_queue: Queue, result_queue: Queue):
    root_logger = logging.getLogger()
    root_logger.setLevel("WARNING")
    logger = logging.getLogger(__name__)

    model_cache: Dict[str, Tuple[Callable, Callable]] = {}

    try:
        for task in iter(task_queue.get, None):
            try:
                if isinstance(task, CacheQuery):
                    cache_key = extract_cache_key(task.resolved_config)
                    is_cached = cache_key in model_cache
                    is_downloaded = (
                        True
                        if is_cached
                        else _is_model_downloaded(
                            _extract_model_name(task.resolved_config)
                        )
                    )
                    result_queue.put(
                        CacheQueryResult(
                            is_cached=is_cached,
                            is_downloaded=is_downloaded,
                        )
                    )
                    continue

                params: DeciderParams = task
                cache_key = extract_cache_key(params.resolved_config)

                if cache_key not in model_cache:
                    old_cleanups = [cleanup for _, (_, cleanup) in model_cache.items()]
                    model_cache.clear()
                    for cleanup in old_cleanups:
                        cleanup()
                    del old_cleanups

                    import torch

                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                        torch.cuda.empty_cache()

                    choose_action_func, cleanup_func = instantiate_adm(
                        params.resolved_config
                    )
                    model_cache[cache_key] = (choose_action_func, cleanup_func)
                else:
                    choose_action_func, _ = model_cache[cache_key]

                result: ADMResult = choose_action_func(params)
                result_queue.put(result)

            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as e:
                logger.error("Worker error:\n%s", traceback.format_exc())
                error_msg = _format_worker_error(e)
                result_queue.put(Exception(error_msg))
    finally:
        for _, (_, cleanup_func) in model_cache.items():
            try:
                cleanup_func()
            except Exception:
                pass


def _format_worker_error(error: Exception) -> str:
    error_text = str(error)
    gated_tokens = (
        "GatedRepoError",
        "gated repo",
        "401 Client Error",
        "Access to model",
        "restricted",
        "Please log in",
    )
    if any(token in error_text for token in gated_tokens):
        return (
            "Model access denied. Authenticate with Hugging Face or request access "
            "to the gated repo."
        )
    return f"{error_text}\n{traceback.format_exc()}"
