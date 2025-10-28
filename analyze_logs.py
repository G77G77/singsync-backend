# Mini tool di debug (eseguibile localmente) per parsare log SSE salvati su file
import json, sys

def main(path):
    with open(path, "r", encoding="utf-8") as f:
        buf = f.read()
    chunks = [c.strip() for c in buf.split("\n\n") if c.strip()]
    for c in chunks:
        lines = c.splitlines()
        event = ""
        data = ""
        for ln in lines:
            if ln.startswith("event: "):
                event = ln[len("event: "):].strip()
            elif ln.startswith("data: "):
                data = ln[len("data: "):].strip()
        try:
            obj = json.loads(data)
        except Exception:
            obj = data
        print(f"[{event}] {obj}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/analyze_logs.py sse_dump.txt")
        sys.exit(1)
    main(sys.argv[1])