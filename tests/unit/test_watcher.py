import asyncio
import os
from pathlib import Path

from tempestroid.cli.watcher import snapshot_mtimes, watch


def test_snapshot_collects_py_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("ignored\n", encoding="utf-8")
    snap = snapshot_mtimes([tmp_path])
    assert tmp_path / "a.py" in snap
    assert tmp_path / "b.txt" not in snap


async def test_watch_fires_on_change(tmp_path: Path):
    app_file = tmp_path / "app.py"
    app_file.write_text("v = 1\n", encoding="utf-8")
    fired = asyncio.Event()

    async def on_change() -> None:
        fired.set()

    task = asyncio.create_task(watch([tmp_path], on_change, interval=0.02))
    await asyncio.sleep(0.05)
    # bump mtime well past the snapshot to defeat coarse filesystem resolution
    new_time = os.stat(app_file).st_mtime + 5
    os.utime(app_file, (new_time, new_time))

    await asyncio.wait_for(fired.wait(), timeout=2.0)
    task.cancel()
