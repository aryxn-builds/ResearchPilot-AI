"""Execute the actual workflow step with mocked curl; no network or credentials required."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/supabase-keepalive.yml").read_text())
STEP = WORKFLOW["jobs"]["health"]["steps"][0]
HEALTHY = {"status": "healthy", "backend": "ok", "database": "ok"}


class KeepaliveTests(unittest.TestCase):
    """Cover scheduler configuration, request safety, retries and failure reporting."""

    def run_check(
        self,
        responses: list[tuple[int, int, object]],
        url: str = "https://example-backend.onrender.com",
        secret: str = "test-monitor-secret",
        watchdog: bool = False,
    ) -> tuple[int, str, list[list[str]], list[str], int]:
        """Run the embedded Python with deterministic curl output and capture its summary."""
        commands, headers = [], []

        def fake_curl(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            commands.append(command)
            headers.append(kwargs["input"])
            self.assertNotIn("HEALTH_CHECK_SECRET", kwargs["env"])
            if watchdog:
                raise subprocess.TimeoutExpired(command, 125, stderr=secret)
            code, status, payload = responses[min(len(commands) - 1, len(responses) - 1)]
            body = payload if isinstance(payload, str) else json.dumps(payload)
            Path(command[command.index("--output") + 1]).write_text(body, encoding="utf-8")
            return subprocess.CompletedProcess(command, code, f"{status:03d} 1.250", secret)

        with tempfile.TemporaryDirectory() as directory:
            summary_path = Path(directory) / "summary.md"
            output = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {
                        "RESEARCHPILOT_BACKEND_URL": url,
                        "HEALTH_CHECK_SECRET": secret,
                        "GITHUB_STEP_SUMMARY": str(summary_path),
                    },
                ),
                patch("subprocess.run", side_effect=fake_curl),
                patch("time.sleep") as sleep,
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(output),
                self.assertRaises(SystemExit) as exited,
            ):
                exec(compile(STEP["run"], "workflow-step", "exec"), {"__name__": "__main__"})
            summary = summary_path.read_text(encoding="utf-8")
            if secret:
                self.assertNotIn(secret, summary + output.getvalue())
                self.assertNotIn(secret, str(commands))
            for call in sleep.call_args_list:
                self.assertEqual(call.args, (20,))
            return exited.exception.code, summary, commands, headers, sleep.call_count

    def test_workflow_structure(self) -> None:
        """Parse YAML and assert scheduling, permissions, triggers and repository configuration."""
        # PyYAML's YAML 1.1 loader resolves the GitHub YAML key 'on' as True.
        triggers = WORKFLOW.get("on", WORKFLOW.get(True))
        self.assertIn("workflow_dispatch", triggers)
        cron = triggers["schedule"][0]["cron"]
        self.assertEqual(cron, "17 */6 * * *")
        self.assertEqual(
            [(h, 17) for h in range(24) if h % 6 == 0], [(0, 17), (6, 17), (12, 17), (18, 17)]
        )
        self.assertEqual(WORKFLOW["permissions"], {"contents": "read"})
        self.assertEqual(
            WORKFLOW["concurrency"],
            {
                "group": "researchpilot-supabase-keepalive",
                "cancel-in-progress": False,
            },
        )
        self.assertIn("github.event.repository.default_branch", WORKFLOW["jobs"]["health"]["if"])
        self.assertEqual(WORKFLOW["jobs"]["health"]["timeout-minutes"], 10)
        self.assertEqual(
            STEP["env"],
            {
                "RESEARCHPILOT_BACKEND_URL": "${{ vars.RESEARCHPILOT_BACKEND_URL }}",
                "HEALTH_CHECK_SECRET": "${{ secrets.HEALTH_CHECK_SECRET }}",
            },
        )
        self.assertEqual(STEP["shell"], "python")
        self.assertEqual(len(WORKFLOW["jobs"]["health"]["steps"]), 1)

    def test_success_and_request_security(self) -> None:
        """Send auth through stdin, enforce HTTPS/timeouts and report the health fields."""
        code, summary, commands, headers, sleeps = self.run_check([(0, 200, HEALTHY)])
        self.assertEqual((code, len(commands), sleeps), (0, 1, 0))
        for expected in (
            "**PASS**",
            "| Backend availability | ok",
            "| Supabase connectivity | ok",
            "| HTTP status (last attempt) | 200",
            "1.250",
            "UTC",
        ):
            self.assertIn(expected, summary)
        command = commands[0]
        for flag, value in (
            ("--proto", "=https"),
            ("--connect-timeout", "15"),
            ("--max-time", "120"),
            ("--request", "GET"),
            ("--header", "@-"),
        ):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertEqual(command[1], "--disable")
        self.assertIn("--fail-with-body", command)
        self.assertNotIn("--insecure", command)
        self.assertNotIn("--location", command)
        self.assertEqual(command[-1], "https://example-backend.onrender.com/api/v1/health/deep")
        self.assertIn("Authorization: Bearer test-monitor-secret\n", headers[0])
        self.assertIn("Cache-Control: no-cache, no-store", headers[0])

    def test_public_mode(self) -> None:
        """Omit authorization when intentionally public and normalize a trailing slash."""
        code, _, commands, headers, _ = self.run_check(
            [(0, 200, HEALTHY)],
            url="https://example.com/",
            secret="",
        )
        self.assertEqual(code, 0)
        self.assertNotIn("Authorization", headers[0])
        self.assertEqual(commands[0][-1], "https://example.com/api/v1/health/deep")

    def test_transient_failures_exhaust_retries(self) -> None:
        """Retry only bounded transient network errors and gateway/database failures."""
        for curl_code, status in ((22, 502), (22, 503), (22, 504), (6, 0), (7, 0), (28, 0)):
            with self.subTest(curl_code=curl_code, status=status):
                code, summary, commands, _, sleeps = self.run_check(
                    [
                        (curl_code, status, {"backend": "ok", "database": "unavailable"}),
                    ]
                )
                self.assertEqual((code, len(commands), sleeps), (1, 3, 2))
                self.assertIn("**FAIL**", summary)

    def test_recovery(self) -> None:
        """A cold-start error can recover on the next attempt."""
        code, _, commands, _, sleeps = self.run_check([(22, 503, {}), (0, 200, HEALTHY)])
        self.assertEqual((code, len(commands), sleeps), (0, 2, 1))

    def test_permanent_failures(self) -> None:
        """Auth failures, redirects, TLS failures and invalid JSON must not be retried."""
        cases = [
            (22, 401, {}),
            (22, 403, {}),
            (22, 404, {}),
            (22, 500, {}),
            (0, 302, HEALTHY),
            (60, 0, {}),
            (0, 200, "not-json"),
            (0, 200, []),
            (0, 200, {}),
            (0, 200, {**HEALTHY, "database": "unavailable"}),
            (0, 200, {**HEALTHY, "status": "unhealthy"}),
            (0, 200, {**HEALTHY, "backend": "failed"}),
        ]
        for response in cases:
            with self.subTest(response=response):
                code, summary, commands, _, sleeps = self.run_check([response])
                self.assertEqual((code, len(commands), sleeps), (1, 1, 0))
                self.assertIn("**FAIL**", summary)

    def test_configuration_fails_before_request(self) -> None:
        """Reject missing URLs, insecure origins, credentials, paths and header injection."""
        for url in (
            "",
            "http://example.com",
            "https://user:pass@example.com",
            "https://example.com/path",
            "https://example.com?q=1",
            "https://example.com#fragment",
            "https://example.com\n",
        ):
            with self.subTest(url=url):
                code, summary, commands, _, _ = self.run_check([], url=url)
                self.assertEqual((code, commands), (1, []))
                self.assertIn("configuration", summary)
        code, _, commands, _, _ = self.run_check([], secret="secret\r\nInjected: value")
        self.assertEqual((code, commands), (1, []))

    def test_watchdog(self) -> None:
        """The outer process timeout also fails after three attempts."""
        code, summary, commands, _, sleeps = self.run_check([], watchdog=True)
        self.assertEqual((code, len(commands), sleeps), (1, 3, 2))
        self.assertIn("125.000", summary)

    def test_response_details_never_logged(self) -> None:
        """Arbitrary response bodies and curl errors never reach log output."""
        code, summary, _, _, _ = self.run_check([(22, 503, "test-monitor-secret")])
        self.assertEqual(code, 1)
        self.assertNotIn("test-monitor-secret", summary)


if __name__ == "__main__":
    unittest.main()
