"""受管浏览器页面适配器资源基础设施测试。"""

from xhs_adapters import managed_page_assets
from xhs_adapters.managed_page_assets import load_managed_page_adapter


def test_managed_page_adapter_asset_is_packaged_and_loadable() -> None:
    """确保共享页面适配器构建产物随 Python 包存在且可以加载。"""
    source = load_managed_page_adapter()

    assert source.strip()
    assert "__XHS_DOWNLOADER_MANAGED_PAGE_ADAPTER__" in source
    assert managed_page_assets._ASSET_NAME == "managed_page_adapter_v2.js"
    assert 'MANAGED_PAGE_ADAPTER_VERSION = "3"' in source
    assert 'MANAGED_ADAPTER_GENERATION = "v2"' in source
    assert 'MANAGED_DIAGNOSTIC_SCHEMA_VERSION = "MANAGED-2"' in source
    assert "proveAccount" in source
    assert "由 apps/extension/build.mjs 生成" in source


def test_legacy_managed_page_adapter_is_not_the_active_load_entry() -> None:
    """确认旧 asset 保留但不再由受管 runtime loader 选择。"""
    assert managed_page_assets._ASSET_NAME != "managed_page_adapter.js"
