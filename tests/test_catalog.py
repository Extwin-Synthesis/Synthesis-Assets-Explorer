import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "extwin" / "synthesis"


def _load(name: str):
    if "extwin" not in sys.modules:
        extwin = types.ModuleType("extwin")
        extwin.__path__ = [str(ROOT / "extwin")]
        sys.modules["extwin"] = extwin
    if "extwin.synthesis" not in sys.modules:
        synthesis = types.ModuleType("extwin.synthesis")
        synthesis.__path__ = [str(PKG)]
        sys.modules["extwin.synthesis"] = synthesis
    full_name = f"extwin.synthesis.{name}"
    spec = importlib.util.spec_from_file_location(full_name, PKG / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "extwin.synthesis"
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


config = _load("config")
catalog = _load("catalog")
app_state = _load("app_state")


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.asset = config.find_asset_type("SimReady")
        config.APP_CONFIG.api_server = "https://synthesis-server.extwin.com"
        config.APP_CONFIG.usd_server = "https://synthesis-multiverse.extwin.com"

    def test_admin_public_uses_system_endpoints(self):
        session = catalog.SessionView(True, True, False)
        self.assertTrue(catalog.category_url(self.asset, "Public", session).endswith("/api/SimReady/GetCategoryList"))
        endpoint = catalog.content_endpoint(self.asset, "Public", session)
        self.assertTrue(endpoint.url.endswith("/api/SimReady/GetSimReadyList"))
        self.assertEqual(endpoint.data_type, 1)

    def test_signed_in_user_public_uses_enterprise_endpoints(self):
        session = catalog.SessionView(False, True, False)
        self.assertTrue(
            catalog.category_url(self.asset, "Public", session).endswith(
                "/api/EnterpriseSimReady/GetCategoryList"
            )
        )
        endpoint = catalog.content_endpoint(self.asset, "Public", session)
        self.assertTrue(endpoint.url.endswith("/api/EnterpriseSimReady/GetSimReadyList"))
        self.assertEqual(endpoint.data_type, 1)

    def test_anonymous_public_uses_free_endpoints(self):
        session = catalog.SessionView(False, False, True)
        self.assertTrue(catalog.category_url(self.asset, "Public", session).endswith("/api/Global/GetCategoryList"))
        endpoint = catalog.content_endpoint(self.asset, "Public", session)
        self.assertTrue(endpoint.url.endswith("/api/Global/GetSimReadyList"))
        self.assertEqual(endpoint.data_type, 1)

    def test_private_uses_enterprise_endpoints_and_private_data_type(self):
        session = catalog.SessionView(False, True, False)
        self.assertTrue(
            catalog.category_url(self.asset, "Private", session).endswith(
                "/api/EnterpriseSimReady/GetCategoryList"
            )
        )
        endpoint = catalog.content_endpoint(self.asset, "Private", session)
        self.assertEqual(endpoint.data_type, 2)

    def test_category_filter_follows_visibility(self):
        items = [{"IsSystem": True, "CategoryName": "sys"}, {"IsSystem": False, "CategoryName": "mine"}]
        self.assertEqual(catalog.filter_categories(items, "Public")[0]["CategoryName"], "sys")
        self.assertEqual(catalog.filter_categories(items, "Private")[0]["CategoryName"], "mine")
        rooted = catalog.with_all_root(catalog.filter_categories(items, "Public"))
        self.assertEqual(rooted[0]["CategoryId"], "All")

    def test_normalize_assets(self):
        scene = [{"Id": 1}]
        self.assertEqual(catalog.normalize_assets("Scene", scene), scene)
        gs = [{"Id": 1, "IsHasUsdFile": True}, {"Id": 2, "IsHasUsdFile": False}]
        self.assertEqual(len(catalog.normalize_assets("_3dGS", gs)), 1)
        model = [{"Id": 3, "IsHasUsdFile": True, "UsdCurrentPath": '["usd/a.usd"]'}]
        normalized = catalog.normalize_assets("Model", model)
        self.assertEqual(normalized[0]["UsdCurrentPath"], ["usd/a.usd"])

    def test_merge_page_replaces_then_appends(self):
        first, has_more, is_append = catalog.merge_page([], [{"Id": 1}], 1, 2, 2)
        self.assertEqual(first, [{"Id": 1}])
        self.assertTrue(has_more)
        self.assertFalse(is_append)
        second, has_more, is_append = catalog.merge_page(first, [{"Id": 2}], 2, 2, 2)
        self.assertEqual([item["Id"] for item in second], [1, 2])
        self.assertFalse(has_more)
        self.assertTrue(is_append)

    def test_search_keeps_category_and_select_clears_keyword(self):
        state = catalog.BrowserState()
        catalog.select_category(state, "cat-1")
        generation = state.generation
        self.assertTrue(catalog.begin_search(state, "robot"))
        self.assertEqual(state.category_id, "cat-1")
        self.assertEqual(state.keyword, "robot")
        self.assertEqual(state.displayed_assets, [])
        self.assertGreater(state.generation, generation)
        self.assertFalse(catalog.begin_search(catalog.BrowserState(), "robot"))

    def test_apply_login_sets_admin_from_user_type(self):
        state = app_state.AppState()
        state._instance = None
        fresh = app_state.AppState()
        self.assertTrue(fresh.apply_login("token", {"UserType": 2, "Name": "a"}))
        self.assertTrue(fresh.is_system_admin)
        self.assertFalse(fresh.is_token_expired)
        self.assertTrue(fresh.apply_login("token", {"UserType": 5}))
        self.assertFalse(fresh.is_system_admin)

    def test_usd_server_change_is_read_at_call_time(self):
        self.assertTrue(catalog.scene_usd_url("scene-1", 1).startswith(config.APP_CONFIG.usd_server))
        config.APP_CONFIG.usd_server = "https://usd.example"
        self.assertTrue(catalog.scene_usd_url("scene-1", 1).startswith("https://usd.example/Scene/scene-1/"))
        url = catalog.drag_usd_url(
            "Model",
            {"IsHasUsdFile": True, "UsdCurrentPath": ["Assets//robot.usd"]},
            1,
        )
        self.assertEqual(url, "https://usd.example/Assets/robot.usd")
        gs = catalog.drag_usd_url("_3dGS", {"IsHasUsdFile": True, "Id": "abc"}, 9)
        self.assertIn("/api/Usd/UsdzFile/abc.usdz?t=9", gs)

    def test_thumbnail_url_has_no_query(self):
        url = catalog.thumbnail_png_url(self.asset, "item-1")
        self.assertTrue(url.endswith("/api/Usd/SimReady/Image/item-1.png"))
        self.assertNotIn("?", url)


if __name__ == "__main__":
    unittest.main()
