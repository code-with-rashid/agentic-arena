"""Opt-in, bounded Docker recipe. Requires a local Linux engine with cgroup v2."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path

from arena.evidence import provenance


def command(*args, timeout=20, **kwargs):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, check=True, **kwargs
    )


def run(image: str):
    info = json.loads(command("info", "--format", "{{json .}}").stdout)
    if info.get("OSType") != "linux" or info.get("CgroupVersion") != "2":
        raise RuntimeError("requires Linux containers with cgroup v2; this host is unsupported")
    # Only an already present image; no implicit registry fetch.
    inspected = json.loads(command("image", "inspect", image).stdout)[0]
    image_id = inspected["Id"]
    name = "arena-isolation-" + uuid.uuid4().hex[:12]
    flags = [
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--memory",
        "128m",
        "--memory-swap",
        "128m",
        "--cpus",
        "0.5",
        "--pids-limit",
        "32",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "65534:65534",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=1048576",
    ]
    probe = Path(__file__).with_name("probe.py")
    created = False
    try:
        command("create", "-i", *flags, image_id, "python", "-")
        created = True
        measured = json.loads(
            command("start", "-ai", name, input=probe.read_text(), timeout=30).stdout
        )
        metadata = json.loads(command("inspect", name).stdout)[0]
        if metadata["State"]["ExitCode"] != 0:
            raise RuntimeError("container probe failed")
        result = {
            "observed": measured,
            "image_id": image_id,
            "repo_digests": inspected.get("RepoDigests", []),
            "docker_server": info["ServerVersion"],
            "flags": flags,
            "provenance": provenance(
                command=["python", "-m", "examples.isolation.recipe", "--image", image],
                mode="offline-fixture",
                configuration={"image_id": image_id, "flags": flags},
                files=[Path(__file__), probe],
                exclusions=[
                    "host escape resistance",
                    "resource exhaustion stress",
                    "network allowlist enforcement",
                    "production credentials",
                ],
            ),
        }
    finally:
        if created:
            command("rm", "-f", name)
            remaining = command("ps", "-aq", "--filter", f"name=^/{name}$").stdout.strip()
            if remaining:
                raise RuntimeError(f"cleanup failed: {name}")
    result["teardown_verified"] = True
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Existing local Python image tag or digest")
    parser.add_argument("--output", type=Path, default=Path("runs/learning/isolation.json"))
    args = parser.parse_args()
    report = run(args.image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
