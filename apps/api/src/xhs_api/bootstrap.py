"""HTTP API 的生产依赖装配。"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from xhs_adapters import (
    BrowserRuntime,
    PublicationRuntime,
    create_browser_runtime,
    create_publication_runtime,
)
from xhs_adapters.config import AppSettings
from xhs_adapters.http import HttpxGateway
from xhs_adapters.settings_repository import DotenvSettingsRepository
from xhs_adapters.sqlite import (
    SqliteClientRecordRepository,
    SqliteCollectionEnrichmentRepository,
    SqliteCollectionMediaArtifactRepository,
    SqliteCollectionRepository,
    SqliteCollectionVideoContentRepository,
    SqliteNoteExtractionRepository,
    SqlitePostRepository,
    SqliteTaskRepository,
)
from xhs_adapters.video import (
    FasterWhisperTranscriber,
    PaddleOcrRecognizer,
    PyAvAudioExtractor,
    PyAvVideoInspector,
    SafeVideoArtifactStore,
)
from xhs_core.application import (
    AtomicClientSlot,
    CollectionDetailEnrichmentService,
    CollectionImportService,
    NoteExtractionService,
    VideoProcessingService,
)
from xhs_core.domain import CollectionMediaArtifactRepository
from xhs_core.domain.ports import (
    ClientRecordRepository,
    PostRepository,
    TaskRepository,
)

from .capability_runtime import (
    ReadCapabilityRuntime,
    create_read_capability_runtime,
)
from .settings_service import SettingsManager


@dataclass(frozen=True)
class ApiDependencies:
    """HTTP API 生命周期所需依赖。"""

    browser: BrowserRuntime
    capabilities: AtomicClientSlot[ReadCapabilityRuntime]
    client_records: ClientRecordRepository
    download_tasks: TaskRepository
    posts: PostRepository
    collection_repository: SqliteCollectionRepository
    collection_import: CollectionImportService
    collection_enrichment: CollectionDetailEnrichmentService
    collection_media_repository: CollectionMediaArtifactRepository
    video_processing: VideoProcessingService
    note_extraction: NoteExtractionService
    video_gateway: HttpxGateway
    publication: PublicationRuntime
    settings: SettingsManager


def create_api_dependencies(
    settings: AppSettings,
    settings_file: Path,
    runtime_overrides: set[str] | None = None,
) -> ApiDependencies:
    """创建 HTTP API 的生产依赖。

    Args:
        settings: 已验证的运行配置。
        settings_file: 管理后台维护的 dotenv 文件。
        runtime_overrides: 启动参数覆盖的配置字段。

    Returns:
        可供 API 生命周期使用的依赖集合。
    """
    database = settings.state_dir.joinpath("downloads.db")
    browser = create_browser_runtime(settings)
    publication = create_publication_runtime(
        settings,
        browser.managed,
        browser.execution_gate,
    )
    capabilities = AtomicClientSlot(
        create_read_capability_runtime(settings, browser, publication)
    )

    async def apply_runtime(
        candidate: AppSettings,
        commit: Callable[[], None],
    ) -> None:
        async def build() -> ReadCapabilityRuntime:
            return create_read_capability_runtime(
                candidate,
                browser,
                publication,
            )

        await capabilities.replace(build, on_commit=commit)

    collection_repository = SqliteCollectionRepository(database)
    enrichment_repository = SqliteCollectionEnrichmentRepository(database)
    collection_media_repository = SqliteCollectionMediaArtifactRepository(database)
    collection_enrichment = CollectionDetailEnrichmentService(
        collection_repository,
        enrichment_repository,
        capabilities.lease,
    )
    video_gateway = HttpxGateway(settings)
    video_media = _CapabilityVideoMediaAcquirer(capabilities)
    video_repository = SqliteCollectionVideoContentRepository(database)
    content_ocr = PaddleOcrRecognizer()
    video_processing = VideoProcessingService(
        collection_repository,
        enrichment_repository,
        video_repository,
        video_media,
        SafeVideoArtifactStore(
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            / "xhs-downloader"
            / "video-content",
            video_gateway,
        ),
        inspector=PyAvVideoInspector(),
        transcriber=FasterWhisperTranscriber(model_size="base"),
        ocr=content_ocr,
        audio_extractor=PyAvAudioExtractor(),
    )
    note_extraction = NoteExtractionService(
        collection_repository,
        enrichment_repository,
        collection_media_repository,
        SqliteNoteExtractionRepository(database),
        video_repository,
        content_ocr,
        settings.output_root,
    )
    return ApiDependencies(
        browser=browser,
        capabilities=capabilities,
        client_records=SqliteClientRecordRepository(database),
        download_tasks=SqliteTaskRepository(database),
        posts=SqlitePostRepository(database),
        collection_repository=collection_repository,
        collection_import=CollectionImportService(collection_repository),
        collection_enrichment=collection_enrichment,
        collection_media_repository=collection_media_repository,
        video_processing=video_processing,
        note_extraction=note_extraction,
        video_gateway=video_gateway,
        publication=publication,
        settings=SettingsManager(
            settings,
            settings_file,
            DotenvSettingsRepository(settings_file),
            runtime_overrides=runtime_overrides,
            apply_runtime=apply_runtime,
        ),
    )


class _CapabilityVideoMediaAcquirer:
    """组合根适配器：从当前只读能力租用媒体定位器。"""

    def __init__(self, capabilities: AtomicClientSlot) -> None:
        self._capabilities = capabilities

    async def acquire(self, feed_id: str, xsec_token: str, request_id: str):
        """从当前能力运行时取得一次性媒体结果。

        Args:
            feed_id: 帖子标识。
            xsec_token: 短期令牌。
            request_id: 请求标识。

        Returns: 不含持久化副作用的媒体结果。
        """
        async with self._capabilities.lease() as runtime:
            result = await runtime.get_feed_media(feed_id, xsec_token, request_id)
            return result.value
