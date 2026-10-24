from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConfig:
    """Servers are read at call time so a settings change is visible to later loads."""

    api_server: str = "https://synthesis-server.extwin.com"
    usd_server: str = "https://synthesis-multiverse.extwin.com"
    web_server: str = "https://synthesis.extwin.com"


APP_CONFIG = AppConfig()


@dataclass(frozen=True)
class AssetType:
    id: str
    name: str
    category_list_path: str
    category_list_free_path: str
    category_list_private_path: str
    content_path: str
    content_free_path: str
    content_private_path: str
    thumbnail_path: str
    type_in_browser: str
    model_business_type: int

    def url(self, path: str) -> str:
        return f"{APP_CONFIG.api_server}{path}"

    @property
    def category_list_url(self) -> str:
        return self.url(self.category_list_path)

    @property
    def category_list_free_url(self) -> str:
        return self.url(self.category_list_free_path)

    @property
    def category_list_private_url(self) -> str:
        return self.url(self.category_list_private_path)

    @property
    def content_url(self) -> str:
        return self.url(self.content_path)

    @property
    def content_free_url(self) -> str:
        return self.url(self.content_free_path)

    @property
    def content_private_url(self) -> str:
        return self.url(self.content_private_path)

    @property
    def thumbnail_url(self) -> str:
        return self.url(self.thumbnail_path)


def _asset(
    asset_id: str,
    name: str,
    category: str,
    category_free: str,
    category_private: str,
    content: str,
    content_free: str,
    content_private: str,
    thumbnail: str,
    type_in_browser: str,
    model_business_type: int,
) -> AssetType:
    return AssetType(
        id=asset_id,
        name=name,
        category_list_path=category,
        category_list_free_path=category_free,
        category_list_private_path=category_private,
        content_path=content,
        content_free_path=content_free,
        content_private_path=content_private,
        thumbnail_path=thumbnail,
        type_in_browser=type_in_browser,
        model_business_type=model_business_type,
    )


ASSET_TYPES: tuple[AssetType, ...] = (
    _asset(
        "SimReady",
        "Sim Ready",
        "/api/SimReady/GetCategoryList",
        "/api/Global/GetCategoryList",
        "/api/EnterpriseSimReady/GetCategoryList",
        "/api/SimReady/GetSimReadyList",
        "/api/Global/GetSimReadyList",
        "/api/EnterpriseSimReady/GetSimReadyList",
        "/api/Usd/SimReady/Image",
        "assets-simready",
        1,
    ),
    _asset(
        "Model",
        "Model",
        "/api/Model/GetCategoryList",
        "/api/Global/GetModelCategoryList",
        "/api/EnterpriseModel/GetCategoryList",
        "/api/Model/GetModelList",
        "/api/Global/GetModelList",
        "/api/EnterpriseModel/GetModelList",
        "/api/Usd/Model/Image",
        "assets-model",
        2,
    ),
    _asset(
        "_3dGS",
        "3D Gauss Splatting",
        "/api/Gs/GetCategoryList",
        "/api/Global/GetGsCategoryList",
        "/api/EnterpriseGs/GetCategoryList",
        "/api/Gs/GetGsList",
        "/api/Global/GetGsList",
        "/api/EnterpriseGs/GetGsList",
        "/api/Usd/Gs/Image",
        "assets-gs",
        3,
    ),
    _asset(
        "Robot",
        "Robot",
        "/api/Noumen/GetCategoryList",
        "/api/Global/GetRobotCategoryList",
        "/api/EnterpriseNoumen/GetCategoryList",
        "/api/Robot/GetRobotList",
        "/api/Global/GetRobotList",
        "/api/EnterpriseRobot/GetRobotList",
        "/api/Usd/Robot/Image",
        "assets-ontology",
        5,
    ),
    _asset(
        "Scene",
        "Scene",
        "/api/Scene/GetCategoryList",
        "/api/Global/GetSceneCategoryList",
        "/api/EnterpriseScene/GetCategoryList",
        "/api/Scene/GetSceneList",
        "/api/Global/GetSceneList",
        "/api/EnterpriseScene/GetSceneList",
        "/api/Usd/Scene/Image",
        "assets-scene",
        6,
    ),
)


def find_asset_type(asset_type_id: str) -> AssetType | None:
    return next((item for item in ASSET_TYPES if item.id == asset_type_id), None)
