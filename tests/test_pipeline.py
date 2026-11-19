"""dy.py 来源分流与批量状态机的离线单测（不联网、不调用真实子进程）。"""

import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("dy", ROOT / "scripts" / "dy.py")
dy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dy)

WX = "https://weixin.qq.com/sph/AiQ59Q9O3y"
DOUYIN = "https://v.douyin.com/abc123/"


def args(output_dir="/tmp/pipeline-out"):
    return argparse.Namespace(output_dir=output_dir, cookies=None,
                              cookies_from_browser=None, quiet=False)


def completed(rc=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


class ClassifyTest(unittest.TestCase):
    def test_douyin_is_ok(self):
        self.assertEqual(dy.classify({"source": "douyin", "aweme_id": "1"}, None),
                         dy.STATUS_OK)

    def test_legacy_meta_without_source_is_ok(self):
        self.assertEqual(dy.classify({"aweme_id": "1"}, None), dy.STATUS_OK)

    def test_client_only_is_media_blocked(self):
        meta = {"source": "weixin-channels", "extraction_status": "metadata_only",
                "playability": "client_only"}
        self.assertEqual(dy.classify(meta, None), dy.STATUS_MEDIA_BLOCKED)

    def test_unknown_playability_is_metadata_only(self):
        meta = {"source": "weixin-channels", "extraction_status": "metadata_only",
                "playability": "unknown"}
        self.assertEqual(dy.classify(meta, None), dy.STATUS_METADATA_ONLY)

    def test_need_login_propagates(self):
        meta = {"source": "weixin-channels", "extraction_status": "need_login"}
        self.assertEqual(dy.classify(meta, None), dy.STATUS_NEED_LOGIN)


class FetchOneTest(unittest.TestCase):
    def test_unsupported_source_never_invokes_subprocess(self):
        err = io.StringIO()
        with mock.patch.object(dy, "run") as run, contextlib.redirect_stderr(err):
            got = dy.fetch_one("https://example.invalid/x", Path("/tmp/work"), args(), False)
        run.assert_not_called()
        self.assertEqual(got, (None, None, dy.STATUS_UNSUPPORTED))
        self.assertIn("unsupported_source", err.getvalue())

    def test_weixin_routes_to_wx_fetch_with_cover_dir(self):
        meta = {"source": "weixin-channels", "source_id": "AiQ59Q9O3y",
                "extraction_status": "metadata_only", "playability": "client_only",
                "audio_path": None}
        with mock.patch.object(dy, "run", return_value=completed(
                stdout=json.dumps(meta, ensure_ascii=False))) as run:
            got = dy.fetch_one(WX, Path("/tmp/work"), args(), True)
        cmd = run.call_args[0][0]
        self.assertTrue(any("wx_fetch.py" in str(part) for part in cmd))
        self.assertIn("--cover-dir", cmd)
        self.assertIn("/tmp/pipeline-out", cmd)
        self.assertIn("-q", cmd)          # quiet=True 透传给适配器
        self.assertEqual(got[0]["source"], "weixin-channels")
        self.assertIsNone(got[1])
        self.assertEqual(got[2], dy.STATUS_MEDIA_BLOCKED)

    def test_douyin_still_routes_to_dy_fetch(self):
        meta = {"aweme_id": "7653", "audio_path": None}
        with mock.patch.object(dy, "run", return_value=completed(
                stdout=json.dumps(meta))) as run:
            got = dy.fetch_one(DOUYIN, Path("/tmp/work"), args(), False)
        cmd = run.call_args[0][0]
        self.assertTrue(any("dy_fetch.py" in str(part) for part in cmd))
        self.assertEqual(got[2], dy.STATUS_OK)

    def test_need_login_error_maps_to_status(self):
        with mock.patch.object(dy, "run", return_value=completed(
                rc=2, stderr="[FAIL] [need_login] 缺少 playwright")):
            got = dy.fetch_one(WX, Path("/tmp/work"), args(), False)
        self.assertIsNone(got[0])
        self.assertEqual(got[2], dy.STATUS_NEED_LOGIN)

    def test_bad_json_is_failed(self):
        with mock.patch.object(dy, "run", return_value=completed(stdout="not-json")):
            got = dy.fetch_one(DOUYIN, Path("/tmp/work"), args(), False)
        self.assertIsNone(got[0])
        self.assertEqual(got[2], "failed")


class SummaryAndLinksTest(unittest.TestCase):
    def test_status_summary_groups(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            dy._print_status_summary({
                WX: dy.STATUS_MEDIA_BLOCKED,
                DOUYIN: dy.STATUS_OK,
                "https://example.invalid/x": dy.STATUS_UNSUPPORTED,
            }, quiet=False)
        text = err.getvalue()
        self.assertIn("[状态清单]", text)
        self.assertIn("media_blocked_by_platform", text)
        self.assertIn("unsupported_source", text)
        self.assertIn("ok", text)

    def test_extract_links_dedup_and_comments(self):
        with mock.patch.object(Path, "is_file", return_value=True), \
             mock.patch.object(Path, "read_text", return_value="# 注释\nA\nA\nB\n"):
            links = dy.extract_links(None, "/tmp/urls.txt")
        self.assertEqual(links, ["A", "B"])


_spec_fetch = importlib.util.spec_from_file_location(
    "dy_fetch", ROOT / "scripts" / "dy_fetch.py")
dyfetch = importlib.util.module_from_spec(_spec_fetch)
_spec_fetch.loader.exec_module(dyfetch)


class NormalizeInputTest(unittest.TestCase):
    def test_trailing_cjk_punctuation_is_stripped(self):
        self.assertEqual(
            dyfetch.normalize_input("复制打开抖音 https://v.douyin.com/abc/）。"),
            "https://v.douyin.com/abc/",
        )

    def test_missing_link_raises(self):
        with self.assertRaises(ValueError):
            dyfetch.normalize_input("纯文字没有链接")

    def test_douyin_ytdlp_command_unchanged(self):
        cmd = dyfetch.build_cmd(DOUYIN, Path("/tmp/out"), None, None, True, False)
        self.assertIn("-m", cmd)
        self.assertIn("yt_dlp", cmd)
        self.assertIn("--write-info-json", cmd)
        self.assertIn("-x", cmd)
        self.assertIn("--audio-format", cmd)
        self.assertEqual(cmd[-1], DOUYIN)


if __name__ == "__main__":
    unittest.main()
