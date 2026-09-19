import React, { useState, useEffect, useMemo } from 'react';
import { ChevronDown, ChevronUp, Copy, Check, ShieldCheck } from 'lucide-react';

interface WebhookViewerProps {
  webhookPayload: object | null;
}

export default function WebhookViewer({ webhookPayload }: WebhookViewerProps) {
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);
  const [status, setStatus] = useState<'PENDING' | 'DISPATCHED'>('PENDING');

  // Trigger dispatched confirmation signal after a 1.5s delay of mount lifecycle
  useEffect(() => {
    setStatus('PENDING');
    const timer = setTimeout(() => {
      setStatus('DISPATCHED');
    }, 1500);
    return () => clearTimeout(timer);
  }, [webhookPayload]);

  // Compute a simple synthetic HMAC-SHA256 checksum for the payload packet
  const hmacSignature = useMemo(() => {
    if (!webhookPayload) return '--------------------';
    const payloadStr = JSON.stringify(webhookPayload);
    // Produce simple hash signature
    let hash = 0;
    for (let i = 0; i < payloadStr.length; i++) {
      const char = payloadStr.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash |= 0; // Convert to 32bit integer
    }
    return 'sha256-' + Math.abs(hash).toString(16).padStart(16, 'e') + 'afb392ee882b4501fa';
  }, [webhookPayload]);

  // Replace default properties with colorful spans according to instructions (without libraries)
  const highlightedJson = useMemo(() => {
    if (!webhookPayload) return '';
    const jsonStr = JSON.stringify(webhookPayload, null, 2);

    // Escape basic HTML elements to prevent vulnerabilities inside JSX dangerouslySetInnerHTML
    const escaped = jsonStr
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    return escaped.replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = 'text-yellow-400'; // number default
        if (match.startsWith('"')) {
          if (match.endsWith(':')) {
            cls = 'text-cyan-400 font-semibold'; // JSON keys
          } else {
            cls = 'text-orange-400'; // string value elements
          }
        } else if (match === 'true' || match === 'false') {
          cls = 'text-purple-400'; // boolean
        } else if (match === 'null') {
          cls = 'text-slate-400'; // Null fallback values
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
  }, [webhookPayload]);

  const copyToClipboard = () => {
    if (!webhookPayload) return;
    navigator.clipboard.writeText(JSON.stringify(webhookPayload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!webhookPayload) return null;

  return (
    <div className="bg-[#03060d] border border-cyan-950/45 rounded-lg shadow-lg overflow-hidden select-none">
      
      {/* Header bar controls */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between p-3 bg-slate-950 border-b border-cyan-950/20 cursor-pointer hover:bg-slate-900/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-cyan-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-cyan-500" />
          )}
          <span className="text-[10px] font-mono tracking-widest text-slate-300 font-semibold uppercase">
            WEBHOOK PAYLOAD
          </span>
        </div>

        <div>
          {status === 'DISPATCHED' ? (
            <span className="text-[8px] font-mono font-bold bg-emerald-950/55 text-emerald-400 border border-emerald-800/40 px-2 py-0.5 rounded shadow-[0_0_8px_rgba(16,185,129,0.1)]">
              DISPATCHED ✓
            </span>
          ) : (
            <span className="text-[8px] font-mono font-bold bg-amber-950/55 text-amber-500 border border-amber-800/40 px-2 py-0.5 rounded animate-pulse">
              PENDING TRANSMISSION
            </span>
          )}
        </div>
      </div>

      {/* Expanded payload segment */}
      {expanded && (
        <div className="p-3.5 space-y-3">
          {/* Main syntax viewer container */}
          <div className="relative bg-[#020509] border border-slate-900 p-3 rounded">
            <pre 
              className="text-[9px] md:text-xs font-mono max-h-[220px] overflow-y-auto leading-normal whitespace-pre scrollbar-thin select-all"
              dangerouslySetInnerHTML={{ __html: highlightedJson }}
            />
          </div>

          {/* Bottom actions strip */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
            {/* HMAC Signature readout */}
            <div className="flex items-center gap-1.5 font-mono text-[9px] text-slate-500">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-600" />
              <span>HMAC SIGNATURE:</span>
              <span className="text-slate-400 bg-slate-950 border border-slate-900/50 px-1 py-0.5 rounded font-mono text-[8.5px]">
                {hmacSignature.slice(0, 20)}...
              </span>
            </div>

            {/* Copy button */}
            <button
              id="btn_copy_json"
              onClick={copyToClipboard}
              className="px-3 py-1 bg-slate-900 border border-cyan-950/60 hover:border-cyan-400 rounded text-[9px] font-mono text-slate-300 hover:text-cyan-400 hover:shadow-[0_0_8px_rgba(34,211,238,0.1)] flex items-center justify-center gap-1 transition-all uppercase cursor-pointer"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  COPIED ✓
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-slate-500" />
                  Copy JSON
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
