"""
ModelLedger Evidence package.

Collects and assembles evidence about digital assets. Nothing in this
package decides authenticity or AI generation; that belongs to the
Evidence Engine / Trust Policy layer.

Importing this package requires neither c2pa-python nor ExifTool; they
are only used when read_c2pa() / read_metadata() are called.
"""

from .ai_signals import (
    AISignal,
    AISignalEvidence,
    AISignalsError,
    AISignalsFileNotFoundError,
    AISignalsReadError,
    InvalidAISignalsFileError,
    collect_ai_signals,
    has_ai_signals,
)
from .c2pa import (
    AI_SOURCE_TYPES,
    C2PAAction,
    C2PACreator,
    C2PAError,
    C2PAEvidence,
    C2PAFileNotFoundError,
    C2PAGenerator,
    C2PAIssue,
    C2PANotInstalledError,
    C2PAReadError,
    C2PASigner,
    InvalidC2PAFileError,
    get_c2pa_validation_state,
    has_c2pa,
    read_c2pa,
)
from .metadata import (
    ExifToolNotFoundError,
    InvalidMetadataFileError,
    MetadataError,
    MetadataEvidence,
    MetadataFileNotFoundError,
    MetadataReadError,
    clean_exiftool_output,
    get_exiftool_version,
    read_metadata,
)
from .model_registry import (
    ModelEntry,
    ModelMatch,
    ModelRegistry,
    find_model,
    resolve_signals,
)
from .receipts import (
    InvalidReceiptError,
    Receipt,
    ReceiptError,
    ToolRecord,
    create_receipt,
    payload_hash,
    verify_chain,
    verify_receipt,
)
from .record import (
    EVIDENCE_PACKAGE_VERSION,
    AssetInfo,
    EvidenceRecord,
    EvidenceSummary,
    InvalidRecordFileError,
    RecordError,
    RecordFileNotFoundError,
    build_record,
    summarize,
)

__all__ = [
    # ai_signals
    "AISignal",
    "AISignalEvidence",
    "AISignalsError",
    "AISignalsFileNotFoundError",
    "AISignalsReadError",
    "InvalidAISignalsFileError",
    "collect_ai_signals",
    "has_ai_signals",
    # c2pa
    "AI_SOURCE_TYPES",
    "C2PAAction",
    "C2PACreator",
    "C2PAError",
    "C2PAEvidence",
    "C2PAFileNotFoundError",
    "C2PAGenerator",
    "C2PAIssue",
    "C2PANotInstalledError",
    "C2PAReadError",
    "C2PASigner",
    "InvalidC2PAFileError",
    "get_c2pa_validation_state",
    "has_c2pa",
    "read_c2pa",
    # metadata
    "ExifToolNotFoundError",
    "InvalidMetadataFileError",
    "MetadataError",
    "MetadataEvidence",
    "MetadataFileNotFoundError",
    "MetadataReadError",
    "clean_exiftool_output",
    "get_exiftool_version",
    "read_metadata",
    # model_registry
    "ModelEntry",
    "ModelMatch",
    "ModelRegistry",
    "find_model",
    "resolve_signals",
    # receipts
    "InvalidReceiptError",
    "Receipt",
    "ReceiptError",
    "ToolRecord",
    "create_receipt",
    "payload_hash",
    "verify_chain",
    "verify_receipt",
    # record
    "EVIDENCE_PACKAGE_VERSION",
    "AssetInfo",
    "EvidenceRecord",
    "EvidenceSummary",
    "InvalidRecordFileError",
    "RecordError",
    "RecordFileNotFoundError",
    "build_record",
    "summarize",
]