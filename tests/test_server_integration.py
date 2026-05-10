import json
import subprocess
import sys


proc = subprocess.Popen(
    [sys.executable, "python/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)


def rpc(req):
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


try:
    assert rpc({"method": "ping"}) == {"pong": True}, "ping failed"

    r = rpc({"method": "platforms"})
    assert "platforms" in r and "x86_64" in r["platforms"]

    src = "struct Foo { int a; char b; double c; };"
    r = rpc(
        {
            "method": "analyse",
            "source": src,
            "language": "c",
            "platform": "x86_64",
            "cache_line": 64,
        }
    )
    assert "structs" in r, r
    assert len(r["structs"]) >= 1
    structs_by_name = {s["name"]: s for s in r["structs"]}
    assert "Foo" in structs_by_name, structs_by_name.keys()
    foo = structs_by_name["Foo"]
    assert foo["layout"]["total_size"] == 16, foo
    assert foo["layout"]["fields"][0]["offset"] == 0, foo
    assert foo["layout"]["fields"][1]["offset"] == 4, foo
    assert foo["layout"]["fields"][2]["offset"] == 8, foo
    assert foo["analysis"]["waste_bytes"] > 0
finally:
    if proc.stdin is not None:
        proc.stdin.close()
    proc.wait(timeout=5)

print("Integration test PASSED")

