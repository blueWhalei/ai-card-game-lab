"""Exercise the actual packaged backend, without models or network services."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def launch(executable: Path, data: Path, log: object):
    env = {**os.environ, "EV_LOSS_ENABLED": "false"}
    process = subprocess.Popen(
        [str(executable), "--data-root", str(data)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=log,
        env=env,
        cwd=str(data),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    ready: queue.Queue[bytes] = queue.Queue()
    threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
    try:
        url = json.loads(ready.get(timeout=60))["url"]
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        client = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        try:
            urllib.request.urlopen(origin + "/api/v1/system/health")
            raise AssertionError("Unauthenticated request was accepted")
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        assert b"<html" in client.open(url).read().lower()
        return process, client, origin
    except BaseException:
        process.kill()
        process.wait()
        raise


def stop(process: subprocess.Popen) -> None:
    process.stdin.close()
    try:
        assert process.wait(timeout=12) == 0
    except BaseException:
        process.kill()
        process.wait()
        raise


def main(executable: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="CardLab 中文 smoke ") as folder:
        data = Path(folder)
        (data / "config.env").write_text("MAX_CONCURRENT_GAMES=2\n", encoding="utf-8")
        with (data / "backend.log").open("wb") as log:
            process, client, origin = launch(executable, data, log)

            def api(path: str, payload: dict | None = None):
                request = urllib.request.Request(
                    origin + "/api/v1/" + path,
                    data=json.dumps(payload).encode() if payload is not None else None,
                    headers={"Content-Type": "application/json", "Origin": origin},
                )
                try:
                    with client.open(request, timeout=30) as response:
                        return json.load(response)["data"]
                except urllib.error.HTTPError as exc:
                    raise RuntimeError(f"{path}: {exc.code}: {exc.read().decode()}") from exc

            try:
                settings = api("system/config")
                assert Path(settings["data_dir"]).resolve() == data.resolve()
                assert Path(settings["config_file"]).resolve() == (data / "config.env").resolve(), (
                    settings["config_file"]
                )
                assert settings["max_concurrent_games"] == 2
                assert api("experiment-configs") == []
                players = []
                for index in range(3):
                    config = api(
                        "experiment-configs",
                        {
                            "id": f"smoke-{index}",
                            "name": f"First {index}",
                            "policy_kind": "first",
                        },
                    )
                    players.append(config["id"])
                experiments = []
                for name in ("Offline A", "Offline B"):
                    experiment = api(
                        "experiments",
                        {
                            "name": name,
                            "player_ids": players,
                            "collect_mode": "benchmark",
                            "target_games": 1,
                        },
                    )
                    eid = experiment["id"]
                    experiments.append(eid)
                    api(f"experiments/{eid}/collect", {"count": 1})
                    deadline = time.monotonic() + 120
                    while time.monotonic() < deadline:
                        detail = api(f"experiments/{eid}")
                        if detail["summary"]["finished_games"] == 1:
                            break
                        if detail.get("games") and all(
                            g["status"] in {"failed", "cancelled", "interrupted"}
                            for g in detail["games"]
                        ):
                            raise AssertionError("Baseline game did not complete")
                        time.sleep(0.25)
                    else:
                        raise TimeoutError("Baseline game exceeded 120 seconds")
                    seats = detail["summary"]["player_stats"]
                    assert len(seats) == 3 and all(s["decided_games"] == 1 for s in seats)
                    assert sum(s["wins"] for s in seats) == {
                        "landlord": 1, "peasant": 2
                    }[detail["games"][0]["winner_role"]]
                snapshot = api(
                    "experiments/comparisons",
                    {"title": "Desktop smoke", "experiment_ids": experiments},
                )
                sid = snapshot["id"]
                coverage = snapshot["result"]["coverage"]
                paired = snapshot["result"]["paired_summary"]
                assert coverage["deal_purpose"] == "development"
                assert coverage["planned_shared"] == coverage["effective_n"] == 1
                assert coverage["excluded_n"] == 0
                assert paired["outcome_counts"]["both_won"] + paired["outcome_counts"]["both_lost"] == 1
                assert paired["win_rate_diff"] == 0 and paired["paired_p"] == 1
                lo, hi = paired["paired_ci"]
                assert abs(lo + 0.9875) < 1e-12 and abs(hi - 0.9875) < 1e-12
                candidates = api(f"experiments/comparisons/{sid}/decisions")
                assert candidates["total"] > 0
                revision = api(
                    f"experiments/comparisons/{sid}/conclusions",
                    {
                        "expected_revision": 0,
                        "observations": "Offline baseline completed",
                        "limitations": "One paired game; packaging smoke only",
                        "evidence": [
                            {
                                "decision_id": candidates["items"][0]["id"],
                                "note": "Smoke evidence",
                            }
                        ],
                    },
                )
                rid = revision["record"]["id"]
                report = api(f"experiments/conclusions/{rid}/export")
                assert report["kind"] == "cardlab.research_report"
                (data / "report.json").write_text(json.dumps(report), encoding="utf-8")
                print(
                    "PASS: session, isolated paths, two baseline games, comparison, cited conclusion and report export"
                )
            except BaseException:
                log.flush()
                print(
                    "\n".join(
                        (data / "backend.log")
                        .read_text(encoding="utf-8", errors="replace")
                        .splitlines()[-45:]
                    )
                )
                raise
            finally:
                stop(process)
            process, client, origin = launch(executable, data, log)
            try:
                assert api(f"experiments/conclusions/{rid}")["record"] == revision["record"]
                print("PASS: graceful shutdown and persistence after restart")
            finally:
                stop(process)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    main(parser.parse_args().executable.resolve())
