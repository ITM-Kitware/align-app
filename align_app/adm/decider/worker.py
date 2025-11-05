import hashlib
import json
import traceback
from typing import Dict, Tuple, Callable, Any
from .executor import instantiate_adm
from .types import DeciderRequest, DeciderResponse, RequestType


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


def decider_process_worker(request_queue, response_queue):
    model_cache: Dict[str, Tuple[Callable, Callable]] = {}

    while True:
        request = None
        try:
            request: DeciderRequest = request_queue.get()

            if request.request_type == RequestType.SHUTDOWN:
                for _, (_, cleanup_func) in model_cache.items():
                    try:
                        cleanup_func()
                    except Exception:
                        pass
                break

            params = request.params
            cache_key = extract_cache_key(params.resolved_config)

            if cache_key not in model_cache:
                choose_action_func, cleanup_func = instantiate_adm(
                    params.resolved_config
                )
                model_cache[cache_key] = (choose_action_func, cleanup_func)
            else:
                choose_action_func, _ = model_cache[cache_key]

            result = choose_action_func(params)

            response = DeciderResponse(
                request_id=request.request_id, result=result, success=True
            )
            response_queue.put(response)

        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            response = DeciderResponse(
                request_id=request.request_id if request else "unknown",
                error=error_msg,
                success=False,
            )
            response_queue.put(response)
