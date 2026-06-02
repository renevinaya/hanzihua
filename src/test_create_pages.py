#!/usr/bin/python3
"""
Standalone test harness to confirm create_pages.py still generates the daily
vocabulary page images after the idna security upgrade.

It stubs out the external I/O that needs credentials/secrets (AWS S3 and the
CC-CEDICT download via requests/idna) and substitutes locally available fonts,
then runs the real page-generation pipeline and checks the produced GIFs.
"""
import gzip
import os
import sqlite3
import sys
import tempfile
from unittest import mock

from PIL import ImageFont

SRC_DIR = os.path.dirname(os.path.abspath(__file__))


def make_pleco_db() -> str:
    """Create a temp sqlite DB matching the Pleco schema the script queries."""
    fd, path = tempfile.mkstemp(prefix="hanzihua-test-")
    os.close(fd)
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("create table pleco_flash_profilesettings (propid text, propvalue text)")
    cur.execute(
        "insert into pleco_flash_profilesettings values ('pro_categories', '1,2,')"
    )
    cur.execute("create table pleco_flash_cards (id integer, hw text, pron text, defn text)")
    cur.execute("create table pleco_flash_scores_1 (card integer, score integer)")
    cur.execute("create table pleco_flash_categoryassigns (card integer, cat integer)")
    cards = [
        (1, "你好", "ni3hao3", "hello"),
        (2, "谢谢", "xie4xie5", "thanks"),
        (3, "学习", "xue2xi2", "to study"),
        (4, "再见", "zai4jian4", "goodbye"),
        (5, "中国", "zhong1guo2", "China"),
    ]
    for cid, hw, pron, defn in cards:
        cur.execute("insert into pleco_flash_cards values (?,?,?,?)", (cid, hw, pron, defn))
        cur.execute("insert into pleco_flash_scores_1 values (?,?)", (cid, cid))
        cur.execute("insert into pleco_flash_categoryassigns values (?,?)", (cid, 1))
    con.commit()
    con.close()
    return path


def fake_cedict_response():
    """A minimal gzipped CC-CEDICT payload returned by the patched requests.get."""
    body = (
        "# comment line\n"
        "你好 你好 [ni3 hao3] /hello/hi/\n"
    ).encode("utf-8")
    resp = mock.MagicMock()
    resp.content = gzip.compress(body)
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: False
    return resp


def fake_boto3_client(db_path):
    def _client(*_args, **_kwargs):
        client = mock.MagicMock()
        client.list_objects_v2.return_value = {"Contents": [{"Key": "pleco/backup.db"}]}

        def _download(Bucket, Key, Filename):  # noqa: N803 (match boto3 kwargs)
            import shutil

            shutil.copyfile(db_path, Filename)

        client.download_file.side_effect = _download
        return client

    return _client


def check_idna() -> None:
    """Confirm the upgraded idna is importable, recent, and functional."""
    import idna

    print(f"idna version: {idna.__version__}")
    major, minor = (int(x) for x in idna.__version__.split(".")[:2])
    assert (major, minor) >= (3, 15), f"idna {idna.__version__} is below the secure floor 3.15"
    # Exercise the actual idna encoding path (used by requests for hostnames).
    assert idna.encode("münchen.de") == b"xn--mnchen-3ya.de"
    print("idna encode() works: münchen.de -> xn--mnchen-3ya.de")


def main() -> int:
    check_idna()

    # Local fallback fonts (container lacks the hardcoded Noto CJK fonts).
    serif = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
    sans = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    real_truetype = ImageFont.truetype

    def patched_truetype(path, size, *a, **k):
        if "CJK" in path or "Serif" in path:
            return real_truetype(serif, size)
        return real_truetype(sans, size)

    db_path = make_pleco_db()
    out_dir = os.path.join(SRC_DIR, "out")
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        if f.endswith(".gif"):
            os.remove(os.path.join(out_dir, f))

    # Provide a stub config module (normally user-supplied with AWS settings).
    config_stub = mock.MagicMock()
    config_stub.REGION = "eu-central-1"
    config_stub.BUCKET = "test-bucket"
    config_stub.PREFIX = "pleco/"
    sys.modules["config"] = config_stub

    sys.path.insert(0, SRC_DIR)
    cwd = os.getcwd()
    os.chdir(SRC_DIR)
    try:
        with mock.patch.object(ImageFont, "truetype", side_effect=patched_truetype), \
             mock.patch("boto3.client", side_effect=fake_boto3_client(db_path)), \
             mock.patch("requests.get", return_value=fake_cedict_response()):
            # Importing the module runs get_ce_ccdict() and main() (page generation).
            import create_pages  # noqa: F401
    finally:
        os.chdir(cwd)
        os.unlink(db_path)

    gifs = sorted(f for f in os.listdir(out_dir) if f.endswith(".gif"))
    print(f"Generated page images: {gifs}")
    assert gifs, "No vocabulary page images were generated!"
    # Verify the files are valid, non-empty images of the expected size.
    from PIL import Image

    for g in gifs:
        with Image.open(os.path.join(out_dir, g)) as im:
            assert im.size == (640, 384), f"{g} has unexpected size {im.size}"
    print(f"SUCCESS: {len(gifs)} valid vocabulary page(s) generated at the expected 640x384.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
