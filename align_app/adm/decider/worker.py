import hashlib
import json
import logging
import traceback
from typing import Dict, Tuple, Callable, Any
from multiprocessing import Queue
from .executor import instantiate_adm
from .types import DeciderParams, ADMResult


def extract_cache_key(resolved_config: Dict[str, Any]) -> str:
    llm_backbone = resolved_config.get("llm_backbone", {})
    model_path_keys = resolved_config.get("model_path_keys", [])

    cache_parts = []
    for key in model_path_keys:
        if key in llm_backbone:
            cache_parts.append(f"{key}={llm_backbone[key]}")

    if not cache_parts:
        cache_str = json.dumps(resolved_config, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()

    return "_".join(cache_parts)


def decider_worker_func(task_queue: Queue, result_queue: Queue):
    root_logger = logging.getLogger()
    root_logger.setLevel("WARNING")

    model_cache: Dict[str, Tuple[Callable, Callable]] = {}

    try:
        for task in iter(task_queue.get, None):
            try:
                params: DeciderParams = task
                cache_key = extract_cache_key(params.resolved_config)

                if cache_key not in model_cache:
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
