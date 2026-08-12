"""Small, replaceable execution boundary for Agent 6 coding tasks."""

from __future__ import annotations

import ast
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


class ProgrammingCodeRunner:
    """Runs curated Python tasks with strict limits.

    This host cannot access Docker, so this implementation is explicitly a demo
    fallback. Production deployments should replace it with the same-contract
    Docker runner service described by the product specification.
    """

    mode = "restricted_subprocess_demo"
    safety_notice = "当前为验收环境受限子进程；生产环境必须切换独立 Docker Sandbox"
    _forbidden_names = {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "globals",
        "input",
        "locals",
        "open",
    }

    def run(self, code: str, tests: list[str]) -> dict[str, Any]:
        started = time.perf_counter()
        violation = self._validate(code)
        if violation:
            return self._result(
                started,
                status="rejected",
                passed=0,
                failed=len(tests),
                error_type="security",
                message=violation,
            )
        harness = self._harness(code, tests)
        try:
            with tempfile.TemporaryDirectory(prefix="agent6_runner_") as directory:
                script = Path(directory) / "submission.py"
                script.write_text(harness, encoding="utf-8")
                completed = subprocess.run(
                    [sys.executable, "-I", "-S", str(script)],
                    cwd=directory,
                    env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0"},
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                    preexec_fn=self._limits if os.name == "posix" else None,
                )
        except subprocess.TimeoutExpired:
            return self._result(
                started,
                status="timeout",
                passed=0,
                failed=len(tests),
                error_type="performance",
                message="执行超过 3 秒，已终止。请检查死循环或复杂度。",
            )
        output = (completed.stdout + completed.stderr)[-4000:]
        passed = output.count("AGENT6_TEST_PASS:")
        failed = max(0, len(tests) - passed)
        if completed.returncode == 0 and failed == 0:
            status, error_type, message = "passed", None, "全部自动测试通过"
        else:
            status = "failed"
            error_type = self._error_type(output)
            message = self._friendly_message(output, error_type)
        return self._result(
            started,
            status=status,
            passed=passed,
            failed=failed,
            error_type=error_type,
            message=message,
            console=output,
        )

    def _validate(self, code: str) -> str | None:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return f"第 {exc.lineno or 1} 行存在语法错误：{exc.msg}"
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return "本训练任务不需要导入模块，执行器已阻止 import"
            if isinstance(node, ast.Name) and node.id in self._forbidden_names:
                return f"执行器已阻止高风险调用：{node.id}"
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return "执行器已阻止访问双下划线内部属性"
        return None

    @staticmethod
    def _harness(code: str, tests: list[str]) -> str:
        blocks = [code, ""]
        for index, test in enumerate(tests, start=1):
            indented = "\n".join(f"    {line}" for line in test.splitlines())
            blocks.append(
                f"try:\n{indented}\n    print('AGENT6_TEST_PASS:{index}')\n"
                f"except Exception as exc:\n    print('AGENT6_TEST_FAIL:{index}:' + "
                "type(exc).__name__ + ':' + str(exc))\n    raise"
            )
        return "\n".join(blocks)

    @staticmethod
    def _limits() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NPROC, (8, 8))

    @staticmethod
    def _error_type(output: str) -> str:
        if "SyntaxError" in output:
            return "syntax"
        if "AssertionError" in output:
            return "logic"
        if "TypeError" in output or "ValueError" in output:
            return "runtime"
        return "runtime"

    @staticmethod
    def _friendly_message(output: str, error_type: str) -> str:
        failed = next((line for line in output.splitlines() if "AGENT6_TEST_FAIL:" in line), "")
        if failed:
            detail = failed.split(":", 3)[-1]
            return f"自动测试发现{error_type}问题：{detail or '结果不符合验收条件'}"
        return "代码未完成测试，请先检查报错位置和输入边界"

    def _result(
        self,
        started: float,
        *,
        status: str,
        passed: int,
        failed: int,
        error_type: str | None,
        message: str,
        console: str = "",
    ) -> dict[str, Any]:
        return {
            "execution_status": status,
            "compile_success": error_type != "syntax",
            "tests_passed": passed,
            "tests_failed": failed,
            "runtime_ms": round((time.perf_counter() - started) * 1000),
            "memory_limit_mb": 128,
            "runner_mode": self.mode,
            "safety_notice": self.safety_notice,
            "error_type": error_type,
            "message": message,
            "console": console,
        }
