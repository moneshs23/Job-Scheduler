import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

TaskHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_REGISTRY: dict[str, TaskHandler] = {}


def task(name: str) -> Callable[[TaskHandler], TaskHandler]:
    def decorator(fn: TaskHandler) -> TaskHandler:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_task(name: str) -> TaskHandler | None:
    return _REGISTRY.get(name)


@task("echo")
async def echo(args: dict[str, Any]) -> dict[str, Any]:
    return {"echoed": args}


@task("sleep")
async def sleep_task(args: dict[str, Any]) -> dict[str, Any]:
    seconds = float(args.get("seconds", 1))
    await asyncio.sleep(seconds)
    return {"slept_seconds": seconds}


@task("http_request")
async def http_request(args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]
    method = args.get("method", "GET").upper()
    async with httpx.AsyncClient(timeout=args.get("timeout", 10)) as client:
        response = await client.request(method, url)
    return {"status_code": response.status_code, "body_preview": response.text[:500]}


@task("fail")
async def fail(args: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError(args.get("message", "Task intentionally failed"))


@task("random_fail")
async def random_fail(args: dict[str, Any]) -> dict[str, Any]:
    failure_rate = float(args.get("failure_rate", 0.5))
    if random.random() < failure_rate:
        raise RuntimeError(f"Random failure triggered (rate={failure_rate})")
    return {"succeeded": True}
