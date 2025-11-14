from __future__ import annotations

import time

from observability.metrics import start_metrics_server


def main(port: int = 8000) -> None:
    print(f"Starting metrics server on :{port}")
    start_metrics_server(port)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Metrics server stopped.")


if __name__ == "__main__":
    main()
