"""
ModelLedger Evidence Package.

Provides components for collecting, validating, and representing
provenance evidence associated with digital assets.

Evidence modules:
- hash: Cryptographic asset hashing
- metadata: File metadata extraction
- c2pa: C2PA provenance verification
- model_registry: AI model identity and version information
- receipts: Generation/execution receipts
- attestation: Execution environment evidence
- record: Unified evidence records
- forensic: Optional forensic evidence
"""

__version__ = "0.1.0"
__author__ = "ModelLedger"

__all__ = [
    "__version__",
    "__author__",
]
