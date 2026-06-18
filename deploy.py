#!/usr/bin/env python3
"""Deploy and manage the LeadFinder service on the Raspberry Pi."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


DEFAULT_PI_HOST = "raspi"
DEFAULT_REMOTE_PATH = "/home/theokoester/dev/leadfinder"
DEFAULT_BRANCH = "main"
SERVICE_NAME = "leadfinder"
HEALTH_PATH = "/api/v1/health"
HEALTH_PORT = 8010
HEALTH_RETRIES = 15
HEALTH_RETRY_DELAY_SEC = 1


@dataclass(slots=True)
class DeployConfig:
    pi_host: str = DEFAULT_PI_HOST
    remote_path: str = DEFAULT_REMOTE_PATH
    branch: str = DEFAULT_BRANCH
    service_name: str = SERVICE_NAME


@dataclass(slots=True)
class SyncPlan:
    up_to_date: bool
    requirements_changed: bool
    local_sha: str
    remote_sha: str


class LeadFinderDeploymentManager:
    def __init__(self, config: DeployConfig | None = None) -> None:
        self.config = config or DeployConfig()

    def _remote_prefix(self) -> str:
        return f"cd {self.config.remote_path}"

    def _ssh(self, remote_script: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = ["ssh", self.config.pi_host, remote_script]
        try:
            return subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            if exc.stderr.strip():
                print(exc.stderr.strip(), file=sys.stderr)
            raise SystemExit(exc.returncode) from exc

    def _run_ssh(self, remote_script: str, *, label: str) -> None:
        print(f"\n→ {label}")
        result = self._ssh(remote_script)
        if result.stdout.strip():
            print(result.stdout.rstrip())
        print(f"✓ {label}")

    def fetch_sync_plan(self) -> SyncPlan:
        branch = self.config.branch
        script = f"""
            set -e
            {self._remote_prefix()}
            git fetch origin
            LOCAL=$(git rev-parse HEAD)
            REMOTE=$(git rev-parse origin/{branch})
            echo "LOCAL_SHA=$LOCAL"
            echo "REMOTE_SHA=$REMOTE"
            if [ "$LOCAL" = "$REMOTE" ]; then
                echo "UP_TO_DATE=1"
                echo "REQUIREMENTS_CHANGED=0"
            else
                echo "UP_TO_DATE=0"
                if git diff --name-only HEAD origin/{branch} | grep -qx requirements.txt; then
                    echo "REQUIREMENTS_CHANGED=1"
                else
                    echo "REQUIREMENTS_CHANGED=0"
                fi
            fi
        """
        print("\n→ Check for updates")
        result = self._ssh(script)
        if result.stdout.strip():
            print(result.stdout.rstrip())

        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()

        plan = SyncPlan(
            up_to_date=values.get("UP_TO_DATE") == "1",
            requirements_changed=values.get("REQUIREMENTS_CHANGED") == "1",
            local_sha=values.get("LOCAL_SHA", "unknown"),
            remote_sha=values.get("REMOTE_SHA", "unknown"),
        )
        print(f"✓ Check for updates ({plan.local_sha[:8]} → {plan.remote_sha[:8]})")
        return plan

    def apply_pull(self, plan: SyncPlan) -> None:
        if plan.up_to_date:
            print("\n… Already on latest commit; skipping git reset")
            return

        branch = self.config.branch
        script = f"""
            set -e
            {self._remote_prefix()}
            echo "Resetting to origin/{branch}..."
            git reset --hard origin/{branch}
        """
        self._run_ssh(script, label="Pull latest code")

    def pull_code(self) -> SyncPlan:
        plan = self.fetch_sync_plan()
        self.apply_pull(plan)
        return plan

    def ensure_venv(self) -> None:
        script = f"""
            set -e
            {self._remote_prefix()}
            if [ ! -d ".venv" ]; then
                echo "Creating virtual environment..."
                python3 -m venv .venv
            else
                echo "Virtual environment already exists."
            fi
        """
        self._run_ssh(script, label="Ensure virtual environment")

    def upgrade_pip(self) -> None:
        script = f"""
            set -e
            {self._remote_prefix()}
            source .venv/bin/activate
            pip install --upgrade pip
        """
        self._run_ssh(script, label="Upgrade pip")

    def install_dependencies(self) -> None:
        script = f"""
            set -e
            {self._remote_prefix()}
            source .venv/bin/activate
            pip install -r requirements.txt
        """
        self._run_ssh(script, label="Install dependencies")

    def restart_service(self) -> None:
        script = f"""
            set -e
            sudo systemctl restart {self.config.service_name}
            echo "Restarted {self.config.service_name}."
        """
        self._run_ssh(script, label=f"Restart {self.config.service_name} service")

    def show_status(self) -> None:
        script = f"""
            set -e
            sudo systemctl --no-pager --lines=20 status {self.config.service_name}
        """
        self._run_ssh(script, label=f"Service status ({self.config.service_name})")

    def check_health(self) -> None:
        script = f"""
            set -e
            url="http://127.0.0.1:{HEALTH_PORT}{HEALTH_PATH}"
            for attempt in $(seq 1 {HEALTH_RETRIES}); do
                if curl -fsS "$url" >/dev/null 2>&1; then
                    curl -fsS "$url"
                    echo
                    echo "Health check passed on attempt $attempt."
                    exit 0
                fi
                if [ "$attempt" -lt {HEALTH_RETRIES} ]; then
                    echo "Waiting for service (attempt $attempt/{HEALTH_RETRIES})..."
                    sleep {HEALTH_RETRY_DELAY_SEC}
                fi
            done
            echo "Health check failed after {HEALTH_RETRIES} attempts." >&2
            exit 1
        """
        self._run_ssh(script, label="Health check")

    def deploy(self, *, install_deps: bool = True, restart: bool = True) -> None:
        print("\n=== LeadFinder Deployment ===")
        print(f"Host: {self.config.pi_host}")
        print(f"Path: {self.config.remote_path}")
        print(f"Branch: origin/{self.config.branch}")

        plan = self.fetch_sync_plan()
        if plan.up_to_date:
            print(f"\n✓ Already up to date at {plan.local_sha[:8]} — nothing to deploy")
            print("\n=== Deployment finished ===\n")
            return

        print(f"\n… Updates available: {plan.local_sha[:8]} → {plan.remote_sha[:8]}")
        self.apply_pull(plan)
        self.ensure_venv()

        should_install_deps = install_deps and plan.requirements_changed
        if should_install_deps:
            self.upgrade_pip()
            self.install_dependencies()
        elif install_deps:
            print("\n… requirements.txt unchanged; skipping dependency install")
        else:
            print("\n… Skipping dependency install (--skip-deps)")

        if restart:
            self.restart_service()
            self.show_status()
            try:
                self.check_health()
            except SystemExit:
                print(
                    "⚠ Health check did not pass in time; "
                    "the service may still be starting.",
                    file=sys.stderr,
                )
        else:
            print("\n… Skipping service restart")

        print("\n=== Deployment finished ===\n")

    def update_dependencies(self, *, restart: bool = False) -> None:
        print("\n=== LeadFinder dependency update ===")
        self.ensure_venv()
        self.upgrade_pip()
        self.install_dependencies()

        if restart:
            self.restart_service()
            self.show_status()
            try:
                self.check_health()
            except SystemExit:
                print(
                    "⚠ Health check did not pass in time; "
                    "the service may still be starting.",
                    file=sys.stderr,
                )

        print("\n=== Dependency update finished ===\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deploy and manage LeadFinder on the Raspberry Pi.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_PI_HOST,
        help=f"SSH host alias (default: {DEFAULT_PI_HOST})",
    )
    parser.add_argument(
        "--path",
        default=DEFAULT_REMOTE_PATH,
        help=f"Remote project path (default: {DEFAULT_REMOTE_PATH})",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=f"Git branch to deploy (default: {DEFAULT_BRANCH})",
    )

    subparsers = parser.add_subparsers(dest="command")

    deploy_parser = subparsers.add_parser("deploy", help="Full deploy: pull, deps, restart")
    parser.set_defaults(command="deploy", skip_deps=False, no_restart=False)
    deploy_parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Never install dependencies, even if requirements.txt changed",
    )
    deploy_parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Pull code without restarting the service",
    )

    deps_parser = subparsers.add_parser(
        "deps",
        help="Reinstall Python dependencies in the remote virtualenv",
    )
    deps_parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart the service after installing dependencies",
    )
    deps_parser.set_defaults(restart=False)

    subparsers.add_parser("pull", help="Fetch and reset to origin/main if updates exist")
    subparsers.add_parser("restart", help="Restart the systemd service")
    subparsers.add_parser("status", help="Show systemd service status")
    subparsers.add_parser("health", help="Call the local /api/v1/health endpoint on the Pi")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    manager = LeadFinderDeploymentManager(
        DeployConfig(
            pi_host=args.host,
            remote_path=args.path,
            branch=args.branch,
        )
    )

    if args.command == "deploy":
        manager.deploy(
            install_deps=not args.skip_deps,
            restart=not args.no_restart,
        )
    elif args.command == "deps":
        manager.update_dependencies(restart=args.restart)
    elif args.command == "pull":
        plan = manager.pull_code()
        if plan.up_to_date:
            print(f"\n✓ Already up to date at {plan.local_sha[:8]}")
    elif args.command == "restart":
        manager.restart_service()
        manager.show_status()
    elif args.command == "status":
        manager.show_status()
    elif args.command == "health":
        manager.check_health()
    else:
        parser.error(f"Unknown command: {args.command}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
