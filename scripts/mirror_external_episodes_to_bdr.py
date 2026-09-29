#!/usr/bin/env python3
"""One-shot, owner-only, read-only live SQLite => isolated BDR mirror proof."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from memoria_resolutiva.external_episode_bdr_mirror import create_verified_mirror


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sqlite", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--bdr-library", type=Path, required=True)
    parser.add_argument("--max-records", type=int, default=100_000)
    arguments = parser.parse_args()
    os.umask(0o077)
    result = create_verified_mirror(
        arguments.source_sqlite, arguments.output_directory,
        library_path=arguments.bdr_library, max_records=arguments.max_records,
    )
    print("V2_BDR_READ_ONLY_MIRROR_OK " + json.dumps(
        result, sort_keys=True, separators=(",", ":"),
    ), flush=True)


if __name__ == "__main__":
    main()
