from __future__ import annotations

from pathlib import Path
import unittest


STATIC_ROOT = Path(__file__).resolve().parents[1] / "app" / "ui" / "static"


class UiStaticAssetsTest(unittest.TestCase):
    def test_index_references_frontend_assets(self) -> None:
        index_path = STATIC_ROOT / "index.html"
        self.assertTrue(index_path.exists())

        body = index_path.read_text(encoding="utf-8")

        self.assertIn('meta name="benchmark-api-base" content="/api"', body)
        self.assertIn('./styles.css', body)
        self.assertIn('./app.js', body)
        self.assertIn("미니 레디스 벤치마크 랩", body)
        self.assertIn('id="hero-spotlight-title"', body)
        self.assertIn('id="hero-spotlight-detail"', body)
        self.assertIn('id="flow-timeline"', body)
        self.assertIn("시간축 흐름 그래프", body)
        self.assertIn("DB / Redis 적중 / Redis 미스", body)
        self.assertIn("supporting-panel", body)

    def test_static_asset_files_exist(self) -> None:
        self.assertTrue((STATIC_ROOT / "styles.css").exists())
        self.assertTrue((STATIC_ROOT / "app.js").exists())

    def test_app_supports_api_base_override_fallback_and_stale_run_guard(self) -> None:
        app_path = STATIC_ROOT / "app.js"
        body = app_path.read_text(encoding="utf-8")

        self.assertIn("benchmark-api-base", body)
        self.assertIn("runRequestToken", body)
        self.assertIn("resolveApiUrl", body)
        self.assertIn("ensureReachableApiBase", body)
        self.assertIn("buildApiBaseCandidates", body)
        self.assertIn("8001", body)
        self.assertIn("8002", body)
        self.assertIn("/api/benchmark-runs/${runId}/requests", body)
        self.assertIn("/api/benchmark-runs/${runId}/presentation", body)
        self.assertIn("renderFlowTimeline", body)
        self.assertIn("renderHeroSpotlight", body)
        self.assertIn("buildRequestNarrative", body)
        self.assertIn("buildStageWindows", body)


if __name__ == "__main__":
    unittest.main()
