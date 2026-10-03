/**
 * ProvLedger API Service Client
 * Outbound client mapping routes to FastAPI backend & local fallback API endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export type VerificationStatus = 'verified' | 'tampered' | 'unregistered';

export interface HistoryEvent {
  action: string;
  model: string;
  version?: string;
  hash: string;
  parent_hash?: string;
  timestamp: string;
}

export interface ArtifactInfo {
  name: string;
  type: string;
  size: string;
  hash: string;
}

export interface OriginInfo {
  model: string;
  version: string;
  action: string;
  timestamp: string;
}

export interface BlockchainInfo {
  block_hash: string;
  block_number: number;
  timestamp: string;
  chain_integrity: boolean;
  previous_hash?: string;
}

export interface VerificationResult {
  status: VerificationStatus;
  artifact: ArtifactInfo;
  origin?: OriginInfo;
  chain_valid: boolean;
  history: HistoryEvent[];
  blockchain?: BlockchainInfo;
  registered_hash?: string;
  current_hash?: string;
}

export type MockMode = 'verified' | 'tampered' | 'unregistered' | 'live';

const MOCK_VERIFIED: VerificationResult = {
  status: 'verified',
  artifact: {
    name: 'ai-generated-image.png',
    type: 'image/png',
    size: '2.4 MB',
    hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
  },
  origin: {
    model: 'Gemini 2.5',
    version: '2.5',
    action: 'GENERATED',
    timestamp: '2026-10-03T20:32:00',
  },
  chain_valid: true,
  history: [
    {
      action: 'GENERATED',
      model: 'Gemini 2.5',
      version: '2.5',
      hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T20:32:00',
    },
    {
      action: 'TRANSFORMED',
      model: 'AI Upscaler Pro',
      version: '1.2',
      hash: '71bc92a1f4e3d7c8b2a5f9e1d4c7b3a6f2e8d5c9b1a4e7f3d6c2b9a5e8f1d4c7',
      parent_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T20:35:00',
    },
    {
      action: 'CURRENT',
      model: 'Current Artifact',
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
};

const MOCK_TAMPERED: VerificationResult = {
  status: 'tampered',
  artifact: {
    name: 'modified-image.png',
    type: 'image/png',
    size: '2.6 MB',
    hash: '91ac72f4b3e6d9c1a5f8e2d7b4c9a3f6e1d8c5b2a9f4e7d3c6b1a8f5e2d9c4b7',
  },
  origin: {
    model: 'Gemini 2.5',
    version: '2.5',
    action: 'GENERATED',
    timestamp: '2026-10-03T20:32:00',
  },
  chain_valid: true,
  history: [
    {
      action: 'GENERATED',
      model: 'Gemini 2.5',
      version: '2.5',
      hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T20:32:00',
    },
    {
      action: 'CURRENT',
      model: 'Unknown',
      hash: '91ac72f4b3e6d9c1a5f8e2d7b4c9a3f6e1d8c5b2a9f4e7d3c6b1a8f5e2d9c4b7',
      parent_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
      timestamp: '2026-10-03T20:41:00',
    },
  ],
  registered_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
  current_hash: '91ac72f4b3e6d9c1a5f8e2d7b4c9a3f6e1d8c5b2a9f4e7d3c6b1a8f5e2d9c4b7',
  blockchain: {
    block_hash: 'e92ab81c4f7d2b9a5e8c3f6d1b4a7e2c9f5d8b3a6e1c4f7d2b9a5e8c3f6d1b4',
    block_number: 3,
    timestamp: '2026-10-03T20:37:00',
    chain_integrity: true,
    previous_hash: '8af32c91b7e4d5f2a19c3e60b74d8f1e2a7c4b9d3e5f8a2c1b7e4d6f3a9c2b5',
  },
};

const MOCK_UNREGISTERED: VerificationResult = {
  status: 'unregistered',
  artifact: {
    name: 'unknown-artifact.png',
    type: 'image/png',
    size: '1.8 MB',
    hash: 'c4b9d3e5f8a2c1b7e4d6f3a9c2b58af32c91b7e4d5f2a19c3e60b74d8f1e2a7',
  },
  chain_valid: false,
  history: [],
};

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

export async function verifyArtifact(
  file: File,
  mockMode: MockMode = 'live'
): Promise<VerificationResult> {
  if (!API_BASE) {
    await new Promise((r) => setTimeout(r, 2000));

    if (mockMode === 'verified') return injectFileInfo(MOCK_VERIFIED, file);
    if (mockMode === 'tampered') return injectFileInfo(MOCK_TAMPERED, file);
    if (mockMode === 'unregistered') return injectFileInfo(MOCK_UNREGISTERED, file);

    return callInternalVerify(file);
  }

  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/verification`, {
    method: 'POST',
    body: formData,
  });
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

async function injectFileInfo(template: VerificationResult, file: File): Promise<VerificationResult> {
  const hash = await computeFileHash(file);
  const size = await getFileSize(file);
  return {
    ...template,
    artifact: {
      ...template.artifact,
      name: file.name,
      type: file.type,
      size,
      hash,
    },
  };
}

async function callInternalVerify(file: File): Promise<VerificationResult> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/api/verify', { method: 'POST', body: formData });
  const data = await res.json();
  const hash = await computeFileHash(file);
  const size = await getFileSize(file);

  if (data.status === 'verified_exact' || data.status === 'verified_transformed') {
    return {
      status: 'verified',
      artifact: { name: file.name, type: file.type, size, hash },
      origin: {
        model: data.record?.model || 'ModelLedger AI',
        version: '1.0',
        action: data.record?.action || 'GENERATED',
        timestamp: data.record?.timestamp || new Date().toISOString(),
      },
      chain_valid: true,
      history: [
        {
          action: data.record?.action || 'GENERATED',
          model: data.record?.model || 'ModelLedger AI',
          hash,
          timestamp: data.record?.timestamp || new Date().toISOString(),
        },
      ],
      blockchain: {
        block_hash: hash,
        block_number: 1,
        timestamp: data.record?.timestamp || new Date().toISOString(),
        chain_integrity: true,
      },
    };
  }

  return {
    status: 'unregistered',
    artifact: { name: file.name, type: file.type, size, hash },
    chain_valid: false,
    history: [],
  };
}

export function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }) + ' · ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

export function truncateHash(hash: string, chars = 12): string {
  if (hash.length <= chars * 2 + 3) return hash;
  return `${hash.slice(0, chars)}...${hash.slice(-6)}`;
}
