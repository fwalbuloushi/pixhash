import os
from datetime import datetime
from typing import List, Tuple


def _sanitize(value: str) -> str:
    """Strip embedded newlines and carriage returns to prevent log injection."""
    return value.replace("\r", " ").replace("\n", " ")


def write_log(
    output_dir: str,
    target: str,
    algo: str,
    user_agent: str,
    results: List[Tuple[str, str]],
    downloaded: bool,
) -> str:
    now = datetime.now()
    log_path = os.path.join(output_dir, f"pixhash_{now.strftime('%Y%m%d_%H%M%S')}.txt")

    with open(log_path, "w") as f:
        f.write("Pixhash Run Log\n")
        f.write("================\n")
        f.write(f"Target URL:    {_sanitize(target)}\n")
        f.write(f"Date:          {now.strftime('%Y-%m-%d')}\n")
        f.write(f"Time:          {now.strftime('%H:%M:%S')}\n")
        f.write(f"Algorithm:     {_sanitize(algo)}\n")
        f.write(f"User-Agent:    {_sanitize(user_agent)}\n")
        f.write(f"Output Dir:    {_sanitize(output_dir)}\n\n")
        f.write("Results\n")
        f.write("-------\n")
        for url, digest in results:
            f.write(f"{_sanitize(url)} >> {digest}\n")
        suffix = (
            "All downloaded images and this log have been saved into:"
            if downloaded
            else "Hash results and log file have been saved into:"
        )
        f.write(f"\n{suffix}\n{_sanitize(output_dir)}\n")

    return log_path
