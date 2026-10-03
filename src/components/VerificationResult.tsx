'use client';

import { motion } from 'framer-motion';
import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  Cpu,
  Calendar,
  Zap,
  ShieldCheck,
  ShieldX,
  Hash,
} from 'lucide-react';
import type { VerificationResult } from '@/services/client';
import { formatTimestamp, truncateHash } from '@/services/client';

interface VerificationResultProps {
  result: VerificationResult;
}

export default function VerificationResultCard({ result }: VerificationResultProps) {
  const isVerified = result.status === 'verified';
  const isTampered = result.status === 'tampered';
  const isUnregistered = result.status === 'unregistered';

  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="w-full max-w-2xl mx-auto"
    >
      {/* Status card */}
      <div
        className={`
          relative rounded-2xl border overflow-hidden
          ${isVerified  ? 'bg-emerald-50/70 border-emerald-200' : ''}
          ${isTampered  ? 'bg-red-50/70   border-red-200'     : ''}
          ${isUnregistered ? 'bg-amber-50/60 border-amber-200' : ''}
        `}
      >
        <div
          className={`
            absolute inset-0 opacity-20 pointer-events-none
            ${isVerified  ? 'bg-gradient-to-br from-emerald-100 to-transparent' : ''}
            ${isTampered  ? 'bg-gradient-to-br from-red-100    to-transparent' : ''}
            ${isUnregistered ? 'bg-gradient-to-br from-amber-100  to-transparent' : ''}
          `}
        />

        <div className="relative p-6 sm:p-8">
          <div className="flex items-start gap-4">
            <motion.div
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.1, type: 'spring', stiffness: 400, damping: 20 }}
              className={`
                w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-sm
                ${isVerified  ? 'bg-emerald-500' : ''}
                ${isTampered  ? 'bg-red-500'     : ''}
                ${isUnregistered ? 'bg-amber-400'  : ''}
              `}
            >
              {isVerified     && <CheckCircle2 className="w-6 h-6 text-white" />}
              {isTampered     && <XCircle      className="w-6 h-6 text-white" />}
              {isUnregistered && <HelpCircle   className="w-6 h-6 text-white" />}
            </motion.div>

            <div className="flex-1 min-w-0">
              <p
                className={`
                  text-[11px] font-bold tracking-[0.18em] uppercase mb-0.5
                  ${isVerified  ? 'text-emerald-600' : ''}
                  ${isTampered  ? 'text-red-600'     : ''}
                  ${isUnregistered ? 'text-amber-600' : ''}
                `}
              >
                {isVerified     && 'PROVENANCE VERIFIED'}
                {isTampered     && 'PROVENANCE FAILED'}
                {isUnregistered && 'NO PROVENANCE RECORD'}
              </p>
              <p className="text-[14px] text-gray-600 leading-relaxed">
                {isVerified &&
                  'This artifact matches a registered provenance record and its integrity chain is valid.'}
                {isTampered &&
                  'The uploaded artifact does not match its registered provenance record.'}
                {isUnregistered &&
                  'Could not find a registered provenance record for this artifact.'}
              </p>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {(isVerified || isTampered) && result.origin && (
              <>
                <EvidenceCell
                  icon={<Cpu className="w-3.5 h-3.5" />}
                  label="ORIGINAL MODEL"
                  value={result.origin.model}
                />
                <EvidenceCell
                  icon={<Zap className="w-3.5 h-3.5" />}
                  label="ACTION"
                  value={result.origin.action}
                />
                <EvidenceCell
                  icon={<Calendar className="w-3.5 h-3.5" />}
                  label="REGISTERED"
                  value={formatTimestamp(result.origin.timestamp)}
                />
              </>
            )}

            <EvidenceCell
              icon={
                result.chain_valid
                  ? <ShieldCheck className="w-3.5 h-3.5" />
                  : <ShieldX className="w-3.5 h-3.5" />
              }
              label="CHAIN STATUS"
              value={result.chain_valid ? '✓ Valid' : '✕ Invalid'}
              valueClass={result.chain_valid ? 'text-emerald-600' : 'text-red-600'}
            />

            <EvidenceCell
              icon={<Hash className="w-3.5 h-3.5" />}
              label="ARTIFACT HASH"
              value={truncateHash(result.artifact.hash, 8)}
              mono
            />

            {isVerified && (
              <EvidenceCell
                icon={<ShieldCheck className="w-3.5 h-3.5" />}
                label="INTEGRITY"
                value="✓ Intact"
                valueClass="text-emerald-600"
              />
            )}

            {isTampered && (
              <>
                <EvidenceCell
                  icon={<Hash className="w-3.5 h-3.5" />}
                  label="REGISTERED HASH"
                  value={truncateHash(result.registered_hash || '', 8)}
                  mono
                />
                <EvidenceCell
                  icon={<XCircle className="w-3.5 h-3.5" />}
                  label="HASH MATCH"
                  value="✕ MISMATCH"
                  valueClass="text-red-600"
                />
                <EvidenceCell
                  icon={<Zap className="w-3.5 h-3.5" />}
                  label="MODIFICATION"
                  value="DETECTED"
                  valueClass="text-red-600"
                />
              </>
            )}

            {isUnregistered && (
              <>
                <EvidenceCell
                  icon={<Cpu className="w-3.5 h-3.5" />}
                  label="MODEL IDENTITY"
                  value="Unknown"
                  valueClass="text-gray-400"
                />
                <EvidenceCell
                  icon={<Calendar className="w-3.5 h-3.5" />}
                  label="REGISTRATION"
                  value="Not Found"
                  valueClass="text-amber-600"
                />
                <EvidenceCell
                  icon={<ShieldX className="w-3.5 h-3.5" />}
                  label="PROVENANCE"
                  value="Unavailable"
                  valueClass="text-gray-400"
                />
              </>
            )}
          </div>
        </div>
      </div>
    </motion.section>
  );
}

function EvidenceCell({
  icon,
  label,
  value,
  mono = false,
  valueClass = '',
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
  valueClass?: string;
}) {
  return (
    <div className="bg-white/60 backdrop-blur-sm rounded-xl border border-black/[0.06] p-3.5">
      <div className="flex items-center gap-1.5 text-gray-400 mb-2">
        {icon}
        <span className="text-[10px] font-semibold tracking-[0.12em] uppercase">{label}</span>
      </div>
      <p
        className={`
          text-[13px] font-semibold leading-tight break-all
          ${mono ? 'font-mono' : ''}
          ${valueClass || 'text-gray-800'}
        `}
      >
        {value}
      </p>
    </div>
  );
}
