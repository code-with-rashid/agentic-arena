"""Runs inside an owned Linux container; checks configuration and small fixtures."""

import errno
import json
import os
from pathlib import Path

assert os.getuid() == 65534
status = Path("/proc/self/status").read_text()
assert "NoNewPrivs:\t1" in status
assert (
    int(next(line.split()[1] for line in status.splitlines() if line.startswith("CapEff:")), 16)
    == 0
)
assert set(os.listdir("/sys/class/net")) == {"lo"}
limits = {
    name: Path("/sys/fs/cgroup", name).read_text().strip()
    for name in ("memory.max", "pids.max", "cpu.max")
}
assert limits["memory.max"] == str(128 * 1024 * 1024)
assert limits["pids.max"] == "32"
quota, period = map(int, limits["cpu.max"].split())
assert quota / period == 0.5
try:
    Path("/var/tmp/arena-owned-probe").write_text("synthetic")
except OSError as exc:
    assert exc.errno == errno.EROFS, exc
else:
    raise AssertionError("root filesystem was writable")
owned = Path("/tmp/arena-owned-probe")
owned.write_text("synthetic")
assert owned.read_text() == "synthetic"
owned.unlink()
mount = next(
    line for line in Path("/proc/mounts").read_text().splitlines() if line.split()[1] == "/tmp"
)
assert all(option in mount.split()[3].split(",") for option in ("nosuid", "noexec"))
print(
    json.dumps(
        {
            "uid": os.getuid(),
            "cgroup_v2": limits,
            "root_read_only": True,
            "owned_tmp_write": True,
            "network_interfaces": ["lo"],
            "no_new_privileges": True,
            "capabilities": 0,
        }
    )
)
