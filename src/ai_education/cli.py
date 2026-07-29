"""Local CLI for serving and inspecting the planner."""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Education agent platform")
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="启动 FastAPI 服务")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    subparsers.add_parser("tools", help="打印规划智能体工具清单")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("ai_education.main:app", host=args.host, port=args.port)
    else:
        from ai_education.api.app import AppContainer

        print(
            json.dumps(
                AppContainer().planner.toolbox.capability_manifest(), ensure_ascii=False, indent=2
            )
        )


if __name__ == "__main__":
    main()
