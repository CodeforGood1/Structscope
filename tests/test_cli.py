import json
import subprocess
import sys
from pathlib import Path


FIXTURE = Path("tests/fixtures/v2_local_demo.c")


def test_cli_json_analyzes_local_c_file():
    result = subprocess.run(
        [sys.executable, "python/cli.py", str(FIXTURE), "--platform", "x86_64", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    structs = {item["name"]: item for item in payload["structs"]}
    assert "TelemetryPacket" in structs
    assert structs["TelemetryPacket"]["analysis"]["waste_bytes"] > 0
    assert structs["TelemetryPacket"]["layout"]["total_size"] == 40
    assert structs["CacheSplitDemo"]["analysis"]["cache_line_splits"]


def test_cli_table_can_filter_struct_by_name():
    result = subprocess.run(
        [
            sys.executable,
            "python/cli.py",
            str(FIXTURE),
            "--platform",
            "x86_64",
            "--struct",
            "TelemetryPacket",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "StructScope CLI" in result.stdout
    assert "TelemetryPacket" in result.stdout
    assert "CompactPacket" not in result.stdout
