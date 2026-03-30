from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    base_url = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

    endpoint = f"https://api.telegram.org/bot{token}/setWebhook"
    payload = {
        "url": f"{base_url}/api/telegram",
    }
    if secret:
        payload["secret_token"] = secret

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response:
        print(json.dumps(json.loads(response.read().decode("utf-8")), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
