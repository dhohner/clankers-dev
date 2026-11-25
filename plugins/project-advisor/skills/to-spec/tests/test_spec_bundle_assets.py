from __future__ import annotations

import unittest

from support import SOURCE_ASSETS


class SpecBundleAssetsTests(unittest.TestCase):
    """Static script guards and bundled font contracts.

    Layout, focus visibility, overflow, and visual preferences require browser
    verification; these tests do not assert stylesheet formatting or appearance.
    """

    def setUp(self) -> None:
        self.script = (SOURCE_ASSETS / "app.js").read_text(encoding="utf-8")

    def test_review_interaction_stays_local_and_read_only(self) -> None:
        script = self.script

        self.assertNotIn("localStorage", script)
        self.assertNotIn("sessionStorage", script)
        self.assertNotIn("fetch(", script)
        self.assertNotIn("XMLHttpRequest", script)
        self.assertNotIn("import(", script)
        self.assertNotIn("prototype", script)
        self.assertNotIn("window.print", script)
        self.assertNotIn("beforeprint", script)

    def test_navigation_is_keyboard_reachable_and_collapses_on_mobile(self) -> None:
        script = self.script

        self.assertIn('return navToggle?.getAttribute("aria-expanded") === "true"', script)
        self.assertIn('navToggle.setAttribute("aria-expanded", String(open))', script)
        self.assertIn('event.key === "Escape"', script)
        self.assertIn("setNavigationOpen(false, true)", script)
        self.assertIn('mobileQuery.addEventListener("change"', script)
        self.assertIn('link.setAttribute("aria-current", "true")', script)

    def test_anchors_clear_the_sticky_chrome_and_move_focus(self) -> None:
        script = self.script

        self.assertIn("headerOffset()", script)
        self.assertIn("focusAnchorTarget(target)", script)
        self.assertIn("target.focus({ preventScroll: true })", script)
        self.assertIn("top: Math.max(0, top)", script)
        self.assertIn('window.addEventListener("hashchange"', script)

    def test_font_and_license_ship_together(self) -> None:
        self.assertTrue((SOURCE_ASSETS / "fonts" / "manrope.woff2").is_file())
        self.assertIn(
            "SIL Open Font License",
            (SOURCE_ASSETS / "fonts" / "OFL-Manrope.txt").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            {"manrope.woff2", "OFL-Manrope.txt"},
            {path.name for path in (SOURCE_ASSETS / "fonts").iterdir()},
        )

    def test_anchor_script_checks_reduced_motion(self) -> None:
        self.assertIn("prefers-reduced-motion: reduce", self.script)
