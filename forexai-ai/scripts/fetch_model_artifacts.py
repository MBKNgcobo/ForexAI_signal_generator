"""Fetch the git-ignored quant artifacts, with checksum verification.

Why this exists
---------------
``models/*.joblib`` is deliberately git-ignored: the three ensemble members
are ~48 MB of environment-specific trained blobs and every developer has
their own copy. The problem is that a *hosted* build (Render, GitHub
Actions, any CI) clones the repository and therefore starts with an empty
``models/`` directory - so the Dockerfile's ``COPY models ./models`` has
nothing to copy and the deployed signal generator silently loses its quant
module.

The fix is to publish the artifacts once, out of band, and pull them at
image-build time. This script reads ``models/ARTIFACTS.sha256`` (sha256sum
format), downloads whatever is missing or corrupt, and refuses to install a
file whose checksum does not match. Artifacts already present and correct
are left alone, so a local build is a no-op.

Usage::

    python scripts/fetch_model_artifacts.py            # fetch what is missing
    python scripts/fetch_model_artifacts.py --check    # offline verify only

Environment:
    MODEL_ARTIFACTS_BASE_URL  Base URL the artifacts are downloaded from.
                              Defaults to the "models-v1" GitHub release of
                              this repository.
    MODEL_ARTIFACTS_DIR       Target directory (default: ``models``).

Standard library only: this runs inside the image before any application
dependency is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("fetch_model_artifacts")

MANIFEST_NAME = "ARTIFACTS.sha256"

DEFAULT_BASE_URL = (
    "https://github.com/MBKNgcobo/ForexAI_signal_generator"
    "/releases/download/models-v1"
)

#: Generous ceiling: the largest member is ~44 MB.
DOWNLOAD_TIMEOUT_SECONDS = 300

CHUNK_SIZE = 1024 * 1024

_HEX_DIGITS = frozenset("0123456789abcdef")


class ArtifactError(RuntimeError):
    """A manifest, download or checksum problem. Always actionable."""



def parse_manifest(text: str) -> dict[str, str]:
    """Parse sha256sum-format text into ``{filename: expected_sha256}``.

    ``#`` starts a comment and blank lines are skipped. Malformed lines
    raise rather than being ignored, because a silently dropped artifact
    would ship a quant ensemble that is quietly incomplete.
    """

    entries: dict[str, str] = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        parts = line.split(None, 1)

        if len(parts) != 2:
            raise ArtifactError(
                f"{MANIFEST_NAME} line {line_number}: expected "
                f"'<sha256>  <file>', got {raw_line!r}"
            )

        digest = parts[0].lower()
        filename = parts[1].strip().lstrip("*")

        if len(digest) != 64 or not set(digest) <= _HEX_DIGITS:
            raise ArtifactError(
                f"{MANIFEST_NAME} line {line_number}: not a sha256 "
                f"digest: {parts[0]!r}"
            )

        if not filename:
            raise ArtifactError(
                f"{MANIFEST_NAME} line {line_number}: missing filename"
            )

        entries[filename] = digest

    if not entries:
        raise ArtifactError(f"{MANIFEST_NAME} contains no artifacts.")

    return entries


def sha256_of(path: Path) -> str:
    """Stream a file through SHA-256 (it can be tens of megabytes)."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)

    return digest.hexdigest()



def download(url: str, destination: Path) -> None:
    """Download ``url`` to ``destination`` atomically, raising on failure."""

    temporary = destination.with_suffix(destination.suffix + ".part")

    try:
        with urllib.request.urlopen(
            url,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            with temporary.open("wb") as handle:
                for chunk in iter(
                    lambda: response.read(CHUNK_SIZE),
                    b"",
                ):
                    handle.write(chunk)

    except urllib.error.HTTPError as exc:
        temporary.unlink(missing_ok=True)
        raise ArtifactError(
            f"Download failed for {url}: HTTP {exc.code} {exc.reason}. "
            f"Upload the artifacts to the release named by "
            f"MODEL_ARTIFACTS_BASE_URL, or point that variable at a mirror."
        ) from exc

    except (urllib.error.URLError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        raise ArtifactError(
            f"Download failed for {url}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    temporary.replace(destination)


def fetch_artifacts(
    artifacts_dir: Path,
    base_url: str,
    check_only: bool = False,
) -> list[str]:
    """Ensure every manifest entry is present and correct.

    Returns the filenames that were downloaded. Raises ``ArtifactError`` on
    a checksum mismatch, a missing manifest or a transport failure.
    """

    manifest_path = artifacts_dir / MANIFEST_NAME

    if not manifest_path.is_file():
        raise ArtifactError(
            f"Manifest not found: {manifest_path}. The models directory "
            f"must be part of the build context."
        )

    expected = parse_manifest(
        manifest_path.read_text(encoding="utf-8")
    )

    artifacts_dir.mkdir(parents=True, exist_ok=True)

    fetched: list[str] = []

    for filename, digest in expected.items():
        target = artifacts_dir / filename

        if target.is_file():
            if sha256_of(target) == digest:
                logger.info("OK (cached) %s", filename)
                continue

            logger.warning(
                "Checksum mismatch for %s (expected %s..., got %s...)",
                filename,
                digest[:12],
                sha256_of(target)[:12],
            )

            if check_only:
                raise ArtifactError(
                    f"{filename} does not match {MANIFEST_NAME}."
                )

        else:
            logger.info("Missing %s", filename)

            if check_only:
                raise ArtifactError(
                    f"{filename} is missing from {artifacts_dir}."
                )

        url = f"{base_url.rstrip('/')}/{filename}"

        logger.info("Downloading %s", url)

        download(url, target)

        actual = sha256_of(target)

        if actual != digest:
            target.unlink(missing_ok=True)
            raise ArtifactError(
                f"{filename} failed checksum verification after download "
                f"(expected {digest}, got {actual}). The corrupt file was "
                f"removed; re-run once the source is fixed."
            )

        logger.info("Verified %s", filename)
        fetched.append(filename)

    return fetched



def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description=(
            "Download the git-ignored quant artifacts listed in "
            "models/ARTIFACTS.sha256."
        )
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify what is on disk without downloading anything.",
    )

    parser.add_argument(
        "--base-url",
        default=None,
        help="Override MODEL_ARTIFACTS_BASE_URL.",
    )

    arguments = parser.parse_args(argv)

    base_url = (
        arguments.base_url
        or os.getenv("MODEL_ARTIFACTS_BASE_URL")
        or DEFAULT_BASE_URL
    )

    artifacts_dir = Path(
        os.getenv("MODEL_ARTIFACTS_DIR", "models")
    )

    try:
        fetched = fetch_artifacts(
            artifacts_dir,
            base_url,
            check_only=arguments.check,
        )
    except ArtifactError as exc:
        logger.error("%s", exc)
        return 1

    if arguments.check:
        logger.info("All artifacts verified in %s.", artifacts_dir)
    elif fetched:
        logger.info(
            "Fetched %d artifact(s): %s",
            len(fetched),
            ", ".join(fetched),
        )
    else:
        logger.info("Nothing to fetch; all artifacts already present.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
