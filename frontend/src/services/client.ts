/**
 * ProvLedger API Service Client
 * Outbound client mapping routes to FastAPI backend & local fallback API endpoints.
 * Supports both image and video artifact types.
 * Structured around 7 Key Provenance Features.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || process.env.NEXT_PUBLIC_API_URL || '';

export type VerificationStatus = 'verified' | 'tampered' | 'unregistered';
export type TrustLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'UNTRUSTED' | 'UNREGISTERED';
export type ArtifactKind = 'image' | 'video';

export interface VideoMetadata {
  duration?: string;        // e.g. "1:24"
  resolution?: string;      // e.g. "1920├ù1080"
  fps?: string;             // e.g. "30 fps"
  codec?: string;           // e.g. "H.264 / AVC"
  frame_count?: number;
  sampling_strategy?: string; // e.g. "Key-frame SHA-256 sampling at 1fps"
}

export interface ArtifactInfo {
  name: string;
  type: string;
  kind: ArtifactKind;
  size: string;
  hash: string;
  video_metadata?: VideoMetadata;
}

export interface HistoryEvent {
  action: string;
  model: string;
  version?: string;
  system_app?: string;
  hash: string;
  parent_hash?: string;
  timestamp: string;
  perceptual_distance?: number;
}

export interface OriginInfo {
  model: string;
  version: string;
  action: string;
  timestamp: string;
  authoring_app?: string;
  creator_id?: string;
}

export interface BlockchainInfo {
  block_hash: string;
  block_number: number;
  timestamp: string;
  chain_integrity: boolean;
  previous_hash?: string;
}

export interface ProvenanceTrust {
  level: TrustLevel;
  label: string;
  verifiable_evidence: boolean;
  evidence_metrics: {
    name: string;
    status: 'pass' | 'warn' | 'fail';
    detail: string;
  }[];
}

export interface TransformationDetails {
  is_transformed: boolean;
  transformation_type?: string;
  perceptual_distance?: number;
  provenance_preserved: boolean;
  similarity_score?: string;
}

export interface MultiSystemProvenance {
  systems_count: number;
  pipeline: {
    system_name: string;
    role: string;
    timestamp: string;
  }[];
}

export interface TamperAnalysis {
  has_tampering: boolean;
  tamper_type?: string;
  inconsistencies: string[];
}

export interface PrivacyShield {
  zero_knowledge_active: boolean;
  salted_prompt_hash: string;
  redacted_fields: string[];
}

export interface AdversarialTestInfo {
  attack_vector?: string;
  resilience_result: string;
  test_category: string;
}

export interface VerificationResult {
  status: VerificationStatus;
  artifact: ArtifactInfo;
  origin?: OriginInfo;
  chain_valid: boolean;
  history: HistoryEvent[];
  blockchain?: BlockchainInfo;

  // 7 Key Feature Extensions
  trust: ProvenanceTrust;
  transformation: TransformationDetails;
  multi_system: MultiSystemProvenance;
  tamper: TamperAnalysis;
  privacy: PrivacyShield;
  adversarial: AdversarialTestInfo;

  registered_hash?: string;
  current_hash?: string;
}

export type MockMode =
  | 'verified'
  | 'transformed'
  | 'tampered'
  | 'privacy'
  | 'unregistered'
  | 'video'
  | 'live';

// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
// BROWSER UTILITY: Extract video metadata from a File object
// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
export async function extractVideoMetadata(file: File): Promise<VideoMetadata> {
  if (typeof document === 'undefined') return {};
  const url = URL.createObjectURL(file);
  return new Promise((resolve) => {
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.src = url;
    video.onloadedmetadata = () => {
      const dur = video.duration;
      const mins = Math.floor(dur / 60);
      const secs = Math.floor(dur % 60);
      resolve({
        duration: isFinite(dur) ? `${mins}:${secs.toString().padStart(2, '0')}` : 'Unknown',
        resolution:
          video.videoWidth && video.videoHeight
            ? `${video.videoWidth}├ù${video.videoHeight}`
            : 'Unknown',
        sampling_strategy: 'Key-frame SHA-256 sampling at 1 fps',
      });
      URL.revokeObjectURL(url);
    };
    video.onerror = () => {
      resolve({ sampling_strategy: 'Key-frame SHA-256 sampling at 1 fps' });
      URL.revokeObjectURL(url);
    };
    // Timeout safety
    setTimeout(() => {
      resolve({ sampling_strategy: 'Key-frame SHA-256 sampling at 1 fps' });
      URL.revokeObjectURL(url);
    }, 5000);
  });
}

// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
// RICH MOCK DATASETS FOR ALL 7 KEY FEATURES
// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

const MOCK_VERIFIED: VerificationResult = {
  status: 'verified',
  artifact: {
    name: 'ai-generated-landscape.png',
    type: 'image/png',
    kind: 'image',
    size: '2.4 MB',
    hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
  },
  origin: {
    model: 'Gemini 2.5',
    version: '2.5 Flash',
    action: 'GENERATED',
    timestamp: '2026-10-03T20:32:00',
    authoring_app: 'Google Imagen Studio',
    creator_id: 'did:key:z6MkpTHR8VNs2e...',
  },
  chain_valid: true,
  history: [
    {
      action: 'GENERATED',
      model: 'Gemini 2.5',
      version: '2.5 Flash',
      system_app: 'Google Imagen Studio',
      hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T20:32:00',
    },
    {
      action: 'TRANSFORMED',
      model: 'AI Upscaler Pro',
      version: '1.2',
      system_app: 'Topaz Gigapixel Pipeline',
      hash: '71bc92a1f4e3d7c8b2a5f9e1d4c7b3a6f2e8d5c9b1a4e7f3d6c2b9a5e8f1d4c7',
      parent_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T20:35:00',
      perceptual_distance: 2,
    },
    {
      action: 'CURRENT',
      model: 'ProvLedger Verified Node',
      system_app: 'ProvLedger Core Inspector',
      hash: '91ac72f4b3e6d9c1a5f8e2d7b4c9a3f6e1d8c5b2a9f4e7d3c6b1a8f5e2d9c4b7',
      parent_hash: '71bc92a1f4e3d7c8b2a5f9e1d4c7b3a6f2e8d5c9b1a4e7f3d6c2b9a5e8f1d4c7',
      timestamp: '2026-10-03T20:37:00',
    },
  ],
  blockchain: {
    block_hash: 'e92ab81c4f7d2b9a5e8c3f6d1b4a7e2c9f5d8b3a6e1c4f7d2b9a5e8c3f6d1b4',
    block_number: 3,
    timestamp: '2026-10-03T20:37:00',
    chain_integrity: true,
    previous_hash: '71bc92a1f4e3d7c8b2a5f9e1d4c7b3a6f2e8d5c9b1a4e7f3d6c2b9a5e8f1d4c7',
  },
  trust: {
    level: 'HIGH',
    label: 'VERIFIABLE EVIDENCE',
    verifiable_evidence: true,
    evidence_metrics: [
      { name: 'C2PA Cryptographic Signature', status: 'pass', detail: 'Signed by Verified Key (Google Trust Root)' },
      { name: 'Merkle Tree Inclusion', status: 'pass', detail: 'Anchored on Block #003' },
      { name: 'HNSW Perceptual Embeddings', status: 'pass', detail: 'Match Confidence: 99.8%' },
    ],
  },
  transformation: { is_transformed: false, provenance_preserved: true, similarity_score: '100% Exact Hash Match' },
  multi_system: {
    systems_count: 2,
    pipeline: [
      { system_name: 'Gemini 2.5 Flash', role: 'Initial Generation Engine', timestamp: '2026-10-03T20:32:00' },
      { system_name: 'AI Upscaler Pro v1.2', role: 'Super Resolution Transform', timestamp: '2026-10-03T20:35:00' },
    ],
  },
  tamper: { has_tampering: false, inconsistencies: [] },
  privacy: {
    zero_knowledge_active: true,
    salted_prompt_hash: '0x9f8b7a6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a',
    redacted_fields: ['User Prompt Text', 'Originating IP Address', 'Custom Style Weights'],
  },
  adversarial: { test_category: 'Standard Multi-System Verification', resilience_result: 'Passed All Integrity Checks' },
};

// ΓöÇΓöÇ Video Verified Mock ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
const MOCK_VIDEO_VERIFIED: VerificationResult = {
  status: 'verified',
  artifact: {
    name: 'ai-generated-cinematic.mp4',
    type: 'video/mp4',
    kind: 'video',
    size: '48.2 MB',
    hash: 'f4a7b2c9e1d5f8a3b6c2e9d4f1a7b3c8e2d6f9a1b4c7e3d2f5a8b1c4e7d0f3a6',
    video_metadata: {
      duration: '0:18',
      resolution: '1920├ù1080',
      fps: '24 fps',
      codec: 'H.264 / AVC',
      frame_count: 432,
      sampling_strategy: 'Key-frame SHA-256 sampling at 1 fps',
    },
  },
  origin: {
    model: 'Sora Video Gen 2.0',
    version: '2.0 (Diffusion)',
    action: 'GENERATED',
    timestamp: '2026-10-03T21:10:00',
    authoring_app: 'OpenAI Sora Studio',
    creator_id: 'did:key:z6Mk4fVdeoX7...',
  },
  chain_valid: true,
  history: [
    {
      action: 'GENERATED',
      model: 'Sora Video Gen 2.0',
      version: '2.0 (Diffusion)',
      system_app: 'OpenAI Sora Studio',
      hash: 'f4a7b2c9e1d5f8a3b6c2e9d4f1a7b3c8e2d6f9a1b4c7e3d2f5a8b1c4e7d0f3a6',
      timestamp: '2026-10-03T21:10:00',
    },
    {
      action: 'RE-ENCODED',
      model: 'H.265 Transcoder Pipeline',
      system_app: 'Media Processing Grid',
      hash: 'a9b3c7e1d5f2a6b0c4e8d2f6a0b4c8e2d6f0a4b8c2e6d0f4a8b2c6e0d4f8a2b6',
      parent_hash: 'f4a7b2c9e1d5f8a3b6c2e9d4f1a7b3c8e2d6f9a1b4c7e3d2f5a8b1c4e7d0f3a6',
      timestamp: '2026-10-03T21:18:00',
      perceptual_distance: 3,
    },
    {
      action: 'CURRENT',
      model: 'ProvLedger Video Inspector',
      system_app: 'ProvLedger Core Inspector',
      hash: 'c2d6f0a4b8c2e6d0f4a8b2c6e0d4f8a2b6c0e4f8a2b6c0e4d8f2a6b0c4e8d2f6',
      parent_hash: 'a9b3c7e1d5f2a6b0c4e8d2f6a0b4c8e2d6f0a4b8c2e6d0f4a8b2c6e0d4f8a2b6',
      timestamp: '2026-10-03T21:20:00',
    },
  ],
  blockchain: {
    block_hash: 'b3c7e1d5f2a6b0c4e8d2f6a0b4c8e2d6f0a4b8c2e6d0f4a8b2c6e0d4f8a2b6c0',
    block_number: 7,
    timestamp: '2026-10-03T21:20:00',
    chain_integrity: true,
    previous_hash: 'a9b3c7e1d5f2a6b0c4e8d2f6a0b4c8e2d6f0a4b8c2e6d0f4a8b2c6e0d4f8a2b6',
  },
  trust: {
    level: 'HIGH',
    label: 'VERIFIABLE EVIDENCE',
    verifiable_evidence: true,
    evidence_metrics: [
      { name: 'Video Key-Frame Sampling (1 fps)', status: 'pass', detail: '432 frames sampled ΓÇö all hashes match ledger commitment' },
      { name: 'C2PA Video Manifest', status: 'pass', detail: 'Signed by OpenAI Trust Root via Ed25519 Key' },
      { name: 'Temporal Hash Merkle Tree', status: 'pass', detail: 'Video segment tree anchored on Block #007' },
      { name: 'Neural Perceptual Embedding (CLIP)', status: 'pass', detail: 'Cosine Similarity: 0.9982 (After re-encoding)' },
    ],
  },
  transformation: {
    is_transformed: true,
    transformation_type: 'H.265 HEVC Re-encoding (Lossless Provenance Transfer)',
    perceptual_distance: 3,
    provenance_preserved: true,
    similarity_score: '99.8% Perceptual Match (Re-encoded)',
  },
  multi_system: {
    systems_count: 2,
    pipeline: [
      { system_name: 'Sora Video Gen 2.0', role: 'Cinematic Video Generator', timestamp: '2026-10-03T21:10:00' },
      { system_name: 'H.265 Transcoder Pipeline', role: 'Codec Re-encoding', timestamp: '2026-10-03T21:18:00' },
    ],
  },
  tamper: { has_tampering: false, inconsistencies: [] },
  privacy: {
    zero_knowledge_active: true,
    salted_prompt_hash: '0x7c3b9a2f1d4e6b8c5a2f9d3e7b1c4a8f2d6e0b3c7a1f5d9e2b6c0f4a8d2e6b0f',
    redacted_fields: ['Video Prompt Tokens', 'Motion Control Parameters', 'Creator Identity'],
  },
  adversarial: {
    test_category: 'Video Provenance Verification (Key-Frame Sampling)',
    resilience_result: 'All 432 Key-Frames Verified ΓÇö Chain Integrity Confirmed',
  },
};

const MOCK_TRANSFORMED: VerificationResult = {
  status: 'verified',
  artifact: {
    name: 'compressed-portrait.webp',
    type: 'image/webp',
    kind: 'image',
    size: '1.1 MB',
    hash: '4a7b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b',
  },
  origin: {
    model: 'DALL-E 3',
    version: '3.0',
    action: 'GENERATED',
    timestamp: '2026-10-03T18:15:00',
    authoring_app: 'OpenAI Image Creator',
  },
  chain_valid: true,
  history: [
    {
      action: 'GENERATED',
      model: 'DALL-E 3',
      version: '3.0',
      system_app: 'OpenAI Studio',
      hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T18:15:00',
    },
    {
      action: 'TRANSFORMED',
      model: 'WebP Compressor / Cropper',
      system_app: 'Media Pipeline Tool',
      hash: '4a7b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b',
      parent_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T19:02:00',
      perceptual_distance: 6,
    },
  ],
  blockchain: {
    block_hash: 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2',
    block_number: 2,
    timestamp: '2026-10-03T19:02:00',
    chain_integrity: true,
    previous_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
  },
  trust: {
    level: 'MEDIUM',
    label: 'TRANSFORMED MATCH',
    verifiable_evidence: true,
    evidence_metrics: [
      { name: 'HNSW Perceptual Vector Search', status: 'pass', detail: 'Visual Match Distance: 6 / 64 bits (Within leniency threshold)' },
      { name: 'C2PA Manifest Re-anchoring', status: 'pass', detail: 'Parent Hash Linked correctly' },
      { name: 'Exact SHA-256 Hash', status: 'warn', detail: 'Modified byte data (Expected for compression)' },
    ],
  },
  transformation: {
    is_transformed: true,
    transformation_type: 'WebP Re-encoding & 5% Crop',
    perceptual_distance: 6,
    provenance_preserved: true,
    similarity_score: '94.2% Perceptual Vector Distance',
  },
  multi_system: {
    systems_count: 2,
    pipeline: [
      { system_name: 'DALL-E 3', role: 'Origin Generator', timestamp: '2026-10-03T18:15:00' },
      { system_name: 'Media Pipeline Tool', role: 'WebP Compression', timestamp: '2026-10-03T19:02:00' },
    ],
  },
  tamper: { has_tampering: false, inconsistencies: [] },
  privacy: {
    zero_knowledge_active: true,
    salted_prompt_hash: '0x3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b',
    redacted_fields: ['Prompt Metadata', 'Author Identity'],
  },
  adversarial: { test_category: 'Transformation Resilience Test', resilience_result: 'Preserved Provenance via Neural Vector Indexing' },
};

const MOCK_TAMPERED: VerificationResult = {
  status: 'tampered',
  artifact: {
    name: 'tampered-deepfake-claim.png',
    type: 'image/png',
    kind: 'image',
    size: '3.1 MB',
    hash: '91ac72f4b3e6d9c1a5f8e2d7b4c9a3f6e1d8c5b2a9f4e7d3c6b1a8f5e2d9c4b7',
  },
  origin: {
    model: 'Gemini 2.5',
    version: '2.5 Flash',
    action: 'GENERATED',
    timestamp: '2026-10-03T20:32:00',
  },
  chain_valid: false,
  history: [
    { action: 'CLAIMED GENERATION', model: 'Gemini 2.5', hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5', timestamp: '2026-10-03T20:32:00' },
    { action: 'UNAUTHORIZED MODIFICATION', model: 'Inconsistent Payload', hash: '91ac72f4b3e6d9c1a5f8e2d7b4c9a3f6e1d8c5b2a9f4e7d3c6b1a8f5e2d9c4b7', parent_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5', timestamp: '2026-10-03T20:41:00' },
  ],
  registered_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
  current_hash: '91ac72f4b3e6d9c1a5f8e2d7b4c9a3f6e1d8c5b2a9f4e7d3c6b1a8f5e2d9c4b7',
  blockchain: {
    block_hash: 'e92ab81c4f7d2b9a5e8c3f6d1b4a7e2c9f5d8b3a6e1c4f7d2b9a5e8c3f6d1b4',
    block_number: 3,
    timestamp: '2026-10-03T20:37:00',
    chain_integrity: false,
    previous_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
  },
  trust: {
    level: 'UNTRUSTED',
    label: 'ADVERSARIAL CONFLICT',
    verifiable_evidence: false,
    evidence_metrics: [
      { name: 'Cryptographic Hash Check', status: 'fail', detail: 'Hash Mismatch: Current artifact does not match registered payload' },
      { name: 'C2PA Signature Verification', status: 'fail', detail: 'Invalid Signature: Manifest payload altered after signing' },
      { name: 'Visual Vector Consistency', status: 'warn', detail: 'Significant Semantic Alteration (Perceptual Distance: 28/64)' },
    ],
  },
  transformation: { is_transformed: true, transformation_type: 'Unauthorized Pixel Inpainting / Deepfake Modification', perceptual_distance: 28, provenance_preserved: false, similarity_score: 'Inconsistent Content Payload' },
  multi_system: {
    systems_count: 1,
    pipeline: [
      { system_name: 'Claimed Gemini 2.5', role: 'Claimed Origin', timestamp: '2026-10-03T20:32:00' },
      { system_name: 'Untrusted Modifier', role: 'Unsigned Modifications', timestamp: '2026-10-03T20:41:00' },
    ],
  },
  tamper: {
    has_tampering: true,
    tamper_type: 'Fabricated Provenance & Payload Alteration',
    inconsistencies: [
      'Artifact content hash differs from ledger commitment',
      'Digital signature broken ΓÇö file modified post-creation',
      'Parent hash reference points to mismatched genesis block',
    ],
  },
  privacy: { zero_knowledge_active: false, salted_prompt_hash: '0x0000000000000000000000000000000000000000000000000000000000000000', redacted_fields: [] },
  adversarial: { test_category: 'Adversarial Deepfake / Payload Modification Attack', attack_vector: 'Fabricated C2PA Manifest & Pixel Inpainting', resilience_result: 'Successfully Identified Inconsistency & Filtered Untrusted Claim' },
};

const MOCK_PRIVACY: VerificationResult = {
  status: 'verified',
  artifact: {
    name: 'confidential-medical-diagram.png',
    type: 'image/png',
    kind: 'image',
    size: '4.2 MB',
    hash: '1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e',
  },
  origin: { model: 'MedAI-Vision 4', version: '4.0 Enterprise', action: 'GENERATED', timestamp: '2026-10-03T22:10:00', authoring_app: 'Secure Health AI Portal' },
  chain_valid: true,
  history: [{ action: 'GENERATED (ZERO-KNOWLEDGE)', model: 'MedAI-Vision 4', system_app: 'Secure Health AI Portal', hash: '1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e', timestamp: '2026-10-03T22:10:00' }],
  blockchain: { block_hash: '7f8e9d0c1b2a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e', block_number: 9, timestamp: '2026-10-03T22:10:00', chain_integrity: true },
  trust: {
    level: 'HIGH',
    label: 'PRIVACY-PRESERVING VERIFIED',
    verifiable_evidence: true,
    evidence_metrics: [
      { name: 'Salted Prompt Commitment', status: 'pass', detail: 'Cryptographic Hash Validated (Zero Knowledge)' },
      { name: 'Redacted Metadata Shield', status: 'pass', detail: 'Sensitive Patient/Prompt Data Excluded from Public Chain' },
      { name: 'C2PA Confidential Manifest', status: 'pass', detail: 'Signed via Institution Private Key' },
    ],
  },
  transformation: { is_transformed: false, provenance_preserved: true, similarity_score: 'Exact Hash Commitment Match' },
  multi_system: { systems_count: 1, pipeline: [{ system_name: 'MedAI-Vision 4 Enterprise', role: 'Shielded Generator', timestamp: '2026-10-03T22:10:00' }] },
  tamper: { has_tampering: false, inconsistencies: [] },
  privacy: {
    zero_knowledge_active: true,
    salted_prompt_hash: '0x88f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7',
    redacted_fields: ['Clinical Prompt', 'Patient Identifiers', 'Facility IP Address', 'Model Hyperparameters'],
  },
  adversarial: { test_category: 'Privacy-Preserving Provenance Check', resilience_result: 'Verified Provenance Without Exposing Sensitive Generation Data' },
};

const MOCK_UNREGISTERED: VerificationResult = {
  status: 'unregistered',
  artifact: {
    name: 'unknown-artifact.png',
    type: 'image/png',
    kind: 'image',
    size: '1.8 MB',
    hash: 'c4b9d3e5f8a2c1b7e4d6f3a9c2b58af32c91b7e4d5f2a19c3e60b74d8f1e2a7',
  },
  chain_valid: false,
  history: [],
  trust: {
    level: 'UNREGISTERED',
    label: 'NO PROVENANCE RECORD',
    verifiable_evidence: false,
    evidence_metrics: [
      { name: 'Ledger Hash Search', status: 'fail', detail: 'No anchor record found on chain' },
      { name: 'C2PA Manifest Inspection', status: 'warn', detail: 'No embedded metadata manifest found' },
    ],
  },
  transformation: { is_transformed: false, provenance_preserved: false },
  multi_system: { systems_count: 0, pipeline: [] },
  tamper: { has_tampering: false, inconsistencies: ['Artifact is not registered on the provenance ledger'] },
  privacy: { zero_knowledge_active: false, salted_prompt_hash: 'None', redacted_fields: [] },
  adversarial: { test_category: 'Unregistered Asset Inspection', resilience_result: 'No Provenance Claim Found' },
};

// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
// UTILITY FUNCTIONS
// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

async function computeFileHash(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function getFileSize(file: File): Promise<string> {
  const bytes = file.size;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function getArtifactKind(type: string): ArtifactKind {
  return type.startsWith('video/') ? 'video' : 'image';
}

async function injectFileInfo(template: VerificationResult, file: File): Promise<VerificationResult> {
  const hash = await computeFileHash(file);
  const size = await getFileSize(file);
  const kind = getArtifactKind(file.type);

  let video_metadata: VideoMetadata | undefined;
  if (kind === 'video') {
    video_metadata = await extractVideoMetadata(file);
  }

  return {
    ...template,
    artifact: {
      ...template.artifact,
      name: file.name,
      type: file.type,
      kind,
      size,
      hash,
      ...(video_metadata ? { video_metadata } : {}),
    },
  };
}

// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
// PUBLIC API FUNCTIONS
// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

export async function verifyArtifact(
  file: File,
  mockMode: MockMode = 'live'
): Promise<VerificationResult> {
  if (!API_BASE) {
    await new Promise((r) => setTimeout(r, 1800));
    if (mockMode === 'verified') return injectFileInfo(MOCK_VERIFIED, file);
    if (mockMode === 'video') return injectFileInfo(MOCK_VIDEO_VERIFIED, file);
    if (mockMode === 'transformed') return injectFileInfo(MOCK_TRANSFORMED, file);
    if (mockMode === 'tampered') return injectFileInfo(MOCK_TAMPERED, file);
    if (mockMode === 'privacy') return injectFileInfo(MOCK_PRIVACY, file);
    if (mockMode === 'unregistered') return injectFileInfo(MOCK_UNREGISTERED, file);
    return callInternalVerify(file);
  }

  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/verification`, { method: 'POST', body: formData });
  if (!res.ok) throw new Error(`Verify failed: ${res.status}`);
  return res.json();
}

export async function registerArtifact(
  file: File,
  metadata?: { model?: string; version?: string; action?: string }
): Promise<{ id: string; hash: string }> {
  const formData = new FormData();
  formData.append('file', file);
  if (metadata?.model) formData.append('model', metadata.model);
  if (metadata?.version) formData.append('version', metadata.version);
  if (metadata?.action) formData.append('action', metadata.action);

  const endpoint = API_BASE ? `${API_BASE}/api/registration` : '/api/register';
  const res = await fetch(endpoint, { method: 'POST', body: formData });
  if (!res.ok) throw new Error(`Register failed: ${res.status}`);

  const hash = await computeFileHash(file);
  return { id: hash.slice(0, 16), hash };
}

async function callInternalVerify(file: File): Promise<VerificationResult> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/api/verify', { method: 'POST', body: formData });
  const data = await res.json();
  const hash = await computeFileHash(file);
  const size = await getFileSize(file);
  const kind = getArtifactKind(file.type);

  let video_metadata: VideoMetadata | undefined;
  if (kind === 'video') {
    video_metadata = await extractVideoMetadata(file);
  }

  if (data.status === 'verified_exact' || data.status === 'verified_transformed') {
    const isTransformed = data.status === 'verified_transformed';
    return {
      status: 'verified',
      artifact: { name: file.name, type: file.type, kind, size, hash, ...(video_metadata ? { video_metadata } : {}) },
      origin: { model: data.record?.model || 'ModelLedger AI', version: '1.0', action: data.record?.action || 'GENERATED', timestamp: data.record?.timestamp || new Date().toISOString() },
      chain_valid: true,
      history: [{ action: data.record?.action || 'GENERATED', model: data.record?.model || 'ModelLedger AI', hash, timestamp: data.record?.timestamp || new Date().toISOString() }],
      blockchain: { block_hash: hash, block_number: 1, timestamp: data.record?.timestamp || new Date().toISOString(), chain_integrity: true },
      trust: {
        level: isTransformed ? 'MEDIUM' : 'HIGH',
        label: isTransformed ? 'TRANSFORMED MATCH' : 'VERIFIABLE EVIDENCE',
        verifiable_evidence: true,
        evidence_metrics: [
          { name: kind === 'video' ? 'Video Key-Frame Hash Match' : 'Ledger Hash Match', status: 'pass', detail: isTransformed ? 'Visual HNSW match verified' : 'Exact SHA-256 match' },
        ],
      },
      transformation: { is_transformed: isTransformed, provenance_preserved: true, similarity_score: isTransformed ? 'Visual Hamming Match' : '100% Exact' },
      multi_system: { systems_count: 1, pipeline: [{ system_name: data.record?.model || 'ModelLedger AI', role: 'Origin Engine', timestamp: new Date().toISOString() }] },
      tamper: { has_tampering: false, inconsistencies: [] },
      privacy: { zero_knowledge_active: true, salted_prompt_hash: '0x' + hash.slice(0, 32), redacted_fields: ['User Prompt String'] },
      adversarial: { test_category: 'Standard Verification', resilience_result: 'Verified Origin' },
    };
  }

  return { ...MOCK_UNREGISTERED, artifact: { name: file.name, type: file.type, kind, size, hash, ...(video_metadata ? { video_metadata } : {}) } };
}

export function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return (
    d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) +
    ' ┬╖ ' +
    d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  );
}

export function truncateHash(hash: string, chars = 12): string {
  if (!hash) return '';
  if (hash.length <= chars * 2 + 3) return hash;
  return `${hash.slice(0, chars)}...${hash.slice(-6)}`;
}
