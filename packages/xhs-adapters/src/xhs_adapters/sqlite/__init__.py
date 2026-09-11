"""SQLite 持久化适配器。"""

from .browser_tasks import SqliteBrowserTaskRepository
from .client_records import SqliteClientRecordRepository
from .collection_enrichments import SqliteCollectionEnrichmentRepository
from .collection_media import SqliteCollectionMediaArtifactRepository
from .collections import SqliteCollectionRepository
from .download_records import SqliteDownloadRepository
from .download_tasks import SqliteTaskRepository
from .extension_credentials import SqliteExtensionCredentialRepository
from .note_extraction import SqliteNoteExtractionRepository
from .posts import SqlitePostRepository
from .publication_drafts import SqlitePublicationDraftRepository
from .publication_tasks import SqlitePublicationTaskRepository
from .video_content import SqliteCollectionVideoContentRepository

__all__ = [
    "SqliteBrowserTaskRepository",
    "SqliteClientRecordRepository",
    "SqliteCollectionEnrichmentRepository",
    "SqliteCollectionMediaArtifactRepository",
    "SqliteCollectionRepository",
    "SqliteCollectionVideoContentRepository",
    "SqliteDownloadRepository",
    "SqliteExtensionCredentialRepository",
    "SqliteNoteExtractionRepository",
    "SqlitePostRepository",
    "SqlitePublicationDraftRepository",
    "SqlitePublicationTaskRepository",
    "SqliteTaskRepository",
]
