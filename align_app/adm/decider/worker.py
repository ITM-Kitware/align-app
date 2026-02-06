import gc
import hashlib
import json
import logging
import traceback
from dataclasses import dataclass
from typing import Dict, Tuple, Callable, Any
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


def decider_worker_func(task_queue: Queue, result_queue: Queue):
    root_logger = logging.getLogger()
    root_logger.setLevel("WARNING")

    model_cache: Dict[str, Tuple[Callable, Callable]] = {}

    try:
        for task in iter(task_queue.get, None):
            try:
                if isinstance(task, CacheQuery):
                    cache_key = extract_cache_key(task.resolved_config)
                    result_queue.put(
                        CacheQueryResult(is_cached=cache_key in model_cache)
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
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                result_queue.put(Exception(error_msg))
    finally:
        for _, (_, cleanup_func) in model_cache.items():
            try:
                cleanup_func()
            except Exception:
                pass
