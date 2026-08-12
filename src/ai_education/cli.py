"""Local CLI for serving and inspecting the planner."""

from __future__ import annotations

import argparse
import getpass
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Education agent platform")
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="启动 FastAPI 服务")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    subparsers.add_parser("tools", help="打印规划智能体工具清单")
    subparsers.add_parser(
        "admin-password-hash",
        help="交互式生成超级管理员密码哈希",
    )
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("ai_education.main:app", host=args.host, port=args.port)
    elif args.command == "tools":
        from ai_education.api.app import AppContainer

        print(
            json.dumps(
                AppContainer().planner.toolbox.capability_manifest(), ensure_ascii=False, indent=2
            )
        )
    else:
        from ai_education.admin import hash_admin_password

        password = getpass.getpass("请输入超级管理员密码（至少 12 个字符）: ")
        confirmation = getpass.getpass("请再次输入密码: ")
        if password != confirmation:
            parser.error("两次输入的密码不一致")
        try:
            print(hash_admin_password(password))
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
