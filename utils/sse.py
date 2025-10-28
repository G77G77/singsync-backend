import json
from typing import Any, Dict

def sse_pack(event: str, data: Dict[str, Any]) -> str:
    """
    Confeziona un evento SSE:
      event: <nome-evento>
      data:  <json>
    """
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\n" + f"data: {payload}\n\n"