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
  Lock,
  AlertOctagon,
  Sliders,
  Layers,
  Sparkles,
  Check,
  AlertTriangle,
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
  const trust = result.trust;
  const privacy = result.privacy;
  const tamper = result.tamper;
  const transformation = result.transformation;

  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="w-full max-w-2xl mx-auto space-y-4"
    >
      {/* Main Status & Trust Card */}
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
          {/* Header Row: Status Icon & Badges */}
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
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span
                  className={`
                    text-[11px] font-bold tracking-[0.18em] uppercase
                    ${isVerified  ? 'text-emerald-700' : ''}
                    ${isTampered  ? 'text-red-700'     : ''}
                    ${isUnregistered ? 'text-amber-700' : ''}
                  `}
                >
                  {isVerified     && 'PROVENANCE VERIFIED'}
                  {isTampered     && 'PROVENANCE FAILED'}
                  {isUnregistered && 'NO PROVENANCE RECORD'}
                </span>

                {/* Trust Level Badge (Feature 2) */}
                {trust && (
                  <span
                    className={`
                      text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider
                      ${trust.level === 'HIGH' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : ''}
                      ${trust.level === 'MEDIUM' ? 'bg-violet-100 text-violet-800 border border-violet-300' : ''}
                      ${trust.level === 'UNTRUSTED' ? 'bg-red-100 text-red-800 border border-red-300' : ''}
                      ${trust.level === 'UNREGISTERED' ? 'bg-amber-100 text-amber-800 border border-amber-300' : ''}
                    `}
                  >
                    TRUST: {trust.label}
                  </span>
                )}

                {/* Privacy Shield Badge (Feature 6) */}
                {privacy?.zero_knowledge_active && (
                  <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-300">
                    <Lock className="w-2.5 h-2.5" /> PRIVACY SHIELD
                  </span>
                )}
              </div>

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

          {/* Evidence Grid (Feature 1 & Feature 2) */}
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
              label="CHAIN INTEGRITY"
              value={result.chain_valid ? 'Γ£ô Valid' : 'Γ£ò Invalid'}
              valueClass={result.chain_valid ? 'text-emerald-600' : 'text-red-600'}
            />

            <EvidenceCell
              icon={<Hash className="w-3.5 h-3.5" />}
              label="ARTIFACT HASH"
              value={truncateHash(result.artifact.hash, 8)}
              mono
            />

            {/* Feature 3: Transformation handling state */}
            {transformation?.is_transformed && (
              <EvidenceCell
                icon={<Sliders className="w-3.5 h-3.5" />}
                label="TRANSFORMATION"
                value={transformation.transformation_type || 'Preserved Edits'}
                valueClass="text-violet-700"
              />
            )}

            {/* Feature 4: Multi-system pipeline count */}
            {result.multi_system?.systems_count > 1 && (
              <EvidenceCell
                icon={<Layers className="w-3.5 h-3.5" />}
                label="MULTI-SYSTEM"
                value={`${result.multi_system.systems_count} AI Engines`}
                valueClass="text-blue-700"
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
                  value="Γ£ò MISMATCH"
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
          </div>
        </div>
      </div>

      {/* Feature 2: Verifiable Evidence Metrics */}
      {trust?.evidence_metrics && trust.evidence_metrics.length > 0 && (
        <div className="bg-white rounded-xl border border-black/[0.06] p-4 space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-gray-400 mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-blue-500" />
            PROVENANCE TRUST & VERIFIABLE EVIDENCE
          </p>
          <div className="space-y-1.5">
            {trust.evidence_metrics.map((metric, i) => (
              <div key={i} className="flex items-start justify-between gap-3 text-xs bg-gray-50/80 p-2.5 rounded-lg border border-gray-100">
                <div className="flex items-center gap-2">
                  {metric.status === 'pass' && <Check className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />}
                  {metric.status === 'warn' && <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />}
                  {metric.status === 'fail' && <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />}
                  <span className="font-semibold text-gray-800">{metric.name}</span>
                </div>
                <span className="text-[11px] text-gray-500 text-right">{metric.detail}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feature 5: Tamper Detection Diagnostic Details */}
      {tamper?.has_tampering && (
        <div className="bg-red-50/80 rounded-xl border border-red-200 p-4 space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-red-600 flex items-center gap-1.5">
            <AlertOctagon className="w-3.5 h-3.5" />
            TAMPER DETECTION DIAGNOSTICS
          </p>
          {tamper.tamper_type && (
            <p className="text-xs font-semibold text-red-800">Attack Type: {tamper.tamper_type}</p>
          )}
          <ul className="space-y-1 pl-4 list-disc text-xs text-red-700">
            {tamper.inconsistencies.map((inc, i) => (
              <li key={i}>{inc}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Feature 6: Privacy-Preserving Salted Prompt Hash */}
      {privacy?.zero_knowledge_active && (
        <div className="bg-blue-50/60 rounded-xl border border-blue-100 p-4 flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
            <Lock className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex-1 text-xs">
            <p className="font-semibold text-blue-900">Privacy-Preserving Salted Prompt Commitment</p>
            <p className="font-mono text-[11px] text-blue-700 mt-0.5 break-all">
              {privacy.salted_prompt_hash}
            </p>
            {privacy.redacted_fields.length > 0 && (
              <p className="text-[11px] text-gray-500 mt-1">
                Protected Fields: {privacy.redacted_fields.join(' ┬╖ ')}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Feature 7: Adversarial Testing Insights */}
      {result.adversarial && (
        <div className="bg-gray-900 text-white rounded-xl p-4 text-xs flex items-center justify-between gap-4 shadow-sm">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              ADVERSARIAL SUITE EVALUATION
            </p>
            <p className="font-medium text-gray-200 mt-0.5">{result.adversarial.test_category}</p>
          </div>
          <span className="px-3 py-1 rounded-full text-[11px] font-semibold bg-blue-600/30 text-blue-300 border border-blue-500/30 whitespace-nowrap">
            {result.adversarial.resilience_result}
          </span>
        </div>
      )}
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
