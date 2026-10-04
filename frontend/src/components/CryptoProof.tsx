'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  Copy,
  Check,
  ShieldCheck,
  ShieldX,
  Hash,
  Clock,
  Blocks,
  Link2,
} from 'lucide-react';
import type { VerificationResult } from '@/services/client';
import { formatTimestamp } from '@/services/client';

interface CryptoProofProps {
  result: VerificationResult;
}

export default function CryptoProof({ result }: CryptoProofProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { artifact, blockchain, chain_valid } = result;

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
      className="w-full max-w-5xl mx-auto"
    >
      <div className="bg-white rounded-2xl border border-black/[0.07] shadow-sm overflow-hidden">
        <button
          onClick={() => setIsOpen((v) => !v)}
          className="w-full flex items-center justify-between px-6 py-5 hover:bg-gray-50/80 transition-colors group"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gray-100 flex items-center justify-center group-hover:bg-gray-200 transition-colors">
              <Blocks className="w-4 h-4 text-gray-500" />
            </div>
            <div className="text-left">
              <p className="text-[13px] font-semibold text-gray-800">CRYPTOGRAPHIC PROOF</p>
              <p className="text-[12px] text-gray-400">View verification evidence</p>
            </div>
          </div>
          <motion.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.25 }}>
            <ChevronDown className="w-4 h-4 text-gray-400" />
          </motion.div>
        </button>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              style={{ overflow: 'hidden' }}
            >
              <div className="border-t border-gray-100 px-6 pb-6 pt-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <ProofRow
                    icon={<Hash className="w-3.5 h-3.5" />}
                    label="Artifact Hash"
                    value={artifact.hash}
                    mono
                    copyable
                  />

                  {blockchain?.previous_hash && (
                    <ProofRow
                      icon={<Link2 className="w-3.5 h-3.5" />}
                      label="Previous Hash"
                      value={blockchain.previous_hash}
                      mono
                      copyable
                    />
                  )}

                  {blockchain?.block_hash && (
                    <ProofRow
                      icon={<Blocks className="w-3.5 h-3.5" />}
                      label="Block Hash"
                      value={blockchain.block_hash}
                      mono
                      copyable
                    />
                  )}

                  {blockchain?.block_number !== undefined && (
                    <ProofRow
                      icon={<Hash className="w-3.5 h-3.5" />}
                      label="Block"
                      value={`#${String(blockchain.block_number).padStart(3, '0')}`}
                      mono
                    />
                  )}

                  {blockchain?.timestamp && (
                    <ProofRow
                      icon={<Clock className="w-3.5 h-3.5" />}
                      label="Timestamp"
                      value={formatTimestamp(blockchain.timestamp)}
                    />
                  )}

                  <ProofRow
                    icon={
                      chain_valid ? (
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                      ) : (
                        <ShieldX className="w-3.5 h-3.5 text-red-500" />
                      )
                    }
                    label="Chain Integrity"
                    value={chain_valid ? '✔ VALID' : '✘ INVALID'}
                    valueClass={chain_valid ? 'text-emerald-600' : 'text-red-600'}
                  />
                </div>

                <p className="mt-5 text-[11px] text-gray-300 leading-relaxed border-t border-gray-100 pt-4">
                  Cryptographic evidence is derived from SHA-256 hashing of the artifact content.
                  Chain integrity validation confirms that each provenance record references the
                  correct predecessor hash.
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.section>
  );
}

function ProofRow({
  icon,
  label,
  value,
  mono = false,
  copyable = false,
  valueClass = '',
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
  copyable?: boolean;
  valueClass?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard not available
    }
  };

  return (
    <div className="bg-gray-50 rounded-xl border border-gray-100 p-3.5 group">
      <div className="flex items-center gap-1.5 text-gray-400 mb-2">
        {icon}
        <span className="text-[10px] font-semibold tracking-[0.12em] uppercase">{label}</span>
      </div>
      <div className="flex items-start gap-2">
        <p
          className={`
            flex-1 text-[12px] leading-relaxed break-all
            ${mono ? 'font-mono' : 'font-medium'}
            ${valueClass || 'text-gray-700'}
          `}
        >
          {value}
        </p>
        {copyable && (
          <button
            onClick={handleCopy}
            className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-lg hover:bg-gray-200"
            title="Copy to clipboard"
          >
            <AnimatePresence mode="wait">
              {copied ? (
                <motion.div
                  key="check"
                  initial={{ scale: 0.7 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0.7 }}
                >
                  <Check className="w-3 h-3 text-emerald-500" />
                </motion.div>
              ) : (
                <motion.div key="copy" initial={{ scale: 0.7 }} animate={{ scale: 1 }}>
                  <Copy className="w-3 h-3 text-gray-400" />
                </motion.div>
              )}
            </AnimatePresence>
          </button>
        )}
      </div>
    </div>
  );
}
