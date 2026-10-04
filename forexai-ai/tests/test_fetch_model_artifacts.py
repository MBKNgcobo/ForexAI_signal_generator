"""The build-time quant artifact fetcher.

The hosted image build starts from a clone, where ``models/*.joblib`` does
not exist. This suite fakes the transport so the manifest parsing, the
checksum gate and the atomic-write behaviour are all pinned without ever
touching the network or the real 44 MB artifacts.
"""

import hashlib
import io
import urllib.error

import pytest

from scripts.fetch_model_artifacts import (
    ArtifactError,
    fetch_artifacts,
    main,
    parse_manifest,
    sha256_of,
)


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def artifacts(tmp_path):
    """A models/ directory holding a manifest and one valid artifact."""

    directory = tmp_path / "models"
    directory.mkdir()

    payload = b"model-bytes"
    (directory / "rf.joblib").write_bytes(payload)

    (directory / "ARTIFACTS.sha256").write_text(
        "# a comment\n"
        "\n"
        f"{_digest(payload)}  rf.joblib\n",
        encoding="utf-8",
    )

    return directory


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def _patch_download(monkeypatch, payload: bytes, recorder: list):
    def _fake_urlopen(url, timeout=None):
        recorder.append(url)
        return _FakeResponse(payload)

    monkeypatch.setattr(
        "scripts.fetch_model_artifacts.urllib.request.urlopen",
        _fake_urlopen,
    )


# --------------------------------------------------------------------------
# Manifest parsing
# --------------------------------------------------------------------------


def test_manifest_parses_sha256sum_format():
    digest = _digest(b"x")

    entries = parse_manifest(
        f"# comment\n\n{digest}  rf.joblib\n{digest} *xgb.joblib\n"
    )

    # The binary-mode marker ("*name") is accepted and normalised away.
    assert entries == {"rf.joblib": digest, "xgb.joblib": digest}


def test_manifest_digest_is_lowercased():
    entries = parse_manifest(f"{_digest(b'x').upper()}  rf.joblib\n")

    assert entries["rf.joblib"] == _digest(b"x")


@pytest.mark.parametrize(
    "text",
    [
        "not-a-digest  rf.joblib\n",
        f"{'a' * 63}  rf.joblib\n",
        "# only comments\n\n",
    ],
)
def test_manifest_rejects_malformed_input(text):
    """A silently skipped line would ship an incomplete quant ensemble."""

    with pytest.raises(ArtifactError):
        parse_manifest(text)


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------


def test_cached_artifact_is_not_downloaded(artifacts, monkeypatch):
    recorder: list = []
    _patch_download(monkeypatch, b"other", recorder)

    assert fetch_artifacts(artifacts, "https://base") == []
    assert recorder == []


def test_missing_artifact_is_downloaded_and_verified(
    artifacts,
    monkeypatch,
):
    (artifacts / "ARTIFACTS.sha256").write_text(
        f"{_digest(b'fresh')}  rf.joblib\n",
        encoding="utf-8",
    )
    (artifacts / "rf.joblib").unlink()

    recorder: list = []
    _patch_download(monkeypatch, b"fresh", recorder)

    assert fetch_artifacts(artifacts, "https://base") == ["rf.joblib"]
    assert recorder == ["https://base/rf.joblib"]
    assert (artifacts / "rf.joblib").read_bytes() == b"fresh"


def test_corrupt_artifact_is_refetched(artifacts, monkeypatch):
    (artifacts / "rf.joblib").write_bytes(b"corrupted")

    recorder: list = []
    _patch_download(monkeypatch, b"model-bytes", recorder)

    assert fetch_artifacts(artifacts, "https://base") == ["rf.joblib"]
    assert len(recorder) == 1


def test_checksum_mismatch_after_download_discards_the_file(
    artifacts,
    monkeypatch,
):
    (artifacts / "rf.joblib").unlink()

    _patch_download(monkeypatch, b"wrong-bytes", [])

    with pytest.raises(ArtifactError, match="checksum"):
        fetch_artifacts(artifacts, "https://base")

    # A corrupt ensemble member must not be left where the loader finds it.
    assert not (artifacts / "rf.joblib").exists()


def test_http_error_is_actionable(artifacts, monkeypatch):
    (artifacts / "rf.joblib").unlink()

    def _fail(url, timeout=None):
        raise urllib.error.HTTPError(
            url,
            404,
            "Not Found",
            {},
            None,
        )

    monkeypatch.setattr(
        "scripts.fetch_model_artifacts.urllib.request.urlopen",
        _fail,
    )

    with pytest.raises(ArtifactError, match="MODEL_ARTIFACTS_BASE_URL"):
        fetch_artifacts(artifacts, "https://base")

    # No partial file left behind.
    assert not list(artifacts.glob("*.part"))


def test_missing_manifest_is_actionable(tmp_path):
    with pytest.raises(ArtifactError, match="Manifest not found"):
        fetch_artifacts(tmp_path / "models", "https://base")


# --------------------------------------------------------------------------
# --check mode and CLI
# --------------------------------------------------------------------------


def test_check_mode_reports_a_missing_artifact(artifacts):
    (artifacts / "rf.joblib").unlink()

    with pytest.raises(ArtifactError, match="missing"):
        fetch_artifacts(artifacts, "https://base", check_only=True)


def test_check_mode_passes_when_everything_matches(artifacts):
    assert fetch_artifacts(artifacts, "https://base", check_only=True) == []


def test_cli_check_exits_zero(artifacts, monkeypatch):
    monkeypatch.setenv("MODEL_ARTIFACTS_DIR", str(artifacts))

    assert main(["--check"]) == 0


def test_cli_returns_one_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_ARTIFACTS_DIR", str(tmp_path / "absent"))

    assert main(["--check"]) == 1


def test_cli_reads_base_url_from_the_environment(artifacts, monkeypatch):
    monkeypatch.setenv("MODEL_ARTIFACTS_DIR", str(artifacts))
    monkeypatch.setenv("MODEL_ARTIFACTS_BASE_URL", "https://mirror/x")

    (artifacts / "ARTIFACTS.sha256").write_text(
        f"{_digest(b'from-mirror')}  rf.joblib\n",
        encoding="utf-8",
    )
    (artifacts / "rf.joblib").unlink()

    recorder: list = []
    _patch_download(monkeypatch, b"from-mirror", recorder)

    assert main([]) == 0
    assert recorder == ["https://mirror/x/rf.joblib"]


def test_sha256_of_matches_hashlib(tmp_path):
    payload = b"a" * (1024 * 64 + 7)
    target = tmp_path / "blob.bin"
    target.write_bytes(payload)

    assert sha256_of(target) == _digest(payload)
