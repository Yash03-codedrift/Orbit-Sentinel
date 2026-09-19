import React, { useEffect, useState } from 'react';
import { X, RotateCcw, Save, Plus, Trash2 } from 'lucide-react';
import { getRiskThresholds, updateRiskBands } from '../api/riskConfigApi';
import { useRiskConfigStore } from '../store/useRiskConfigStore';

interface RiskConfigPanelProps {
  onClose: () => void;
}

interface DraftBand {
  key: string;
  min_score: string;
  color: string;
}

const NEW_BAND_COLOR = '#8B5CF6';

export default function RiskConfigPanel({ onClose }: RiskConfigPanelProps) {
  const [draft, setDraft] = useState<DraftBand[]>([]);
  const [defaults, setDefaults] = useState<DraftBand[]>([]);
  const [minBands, setMinBands] = useState(2);
  const [maxBands, setMaxBands] = useState(6);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res: any = await getRiskThresholds();
        if (!active) return;
        const toDraft = (b: any[]) => b.map((x) => ({ key: x.key, min_score: String(x.min_score), color: x.color }));
        setDraft(toDraft(res.bands));
        setDefaults(toDraft(res.defaults));
        setMinBands(res.min_bands ?? 2);
        setMaxBands(res.max_bands ?? 6);
      } catch (err) {
        if (active) setError('Failed to load risk bands.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  const handleFieldChange = (idx: number, field: keyof DraftBand, value: string) => {
    setDraft((prev) => prev.map((b, i) => (i === idx ? { ...b, [field]: value } : b)));
  };

  const handleAddBand = () => {
    if (draft.length >= maxBands) return;
    setDraft((prev) => [...prev, { key: `BAND_${prev.length + 1}`, min_score: '0.001', color: NEW_BAND_COLOR }]);
  };

  const handleRemoveBand = (idx: number) => {
    if (draft.length <= minBands) return;
    setDraft((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleResetDefaults = () => setDraft(defaults);

  const handleSave = async () => {
    setError(null);

    if (draft.length < minBands || draft.length > maxBands) {
      setError(`Must have between ${minBands} and ${maxBands} bands.`);
      return;
    }

    const parsed = [];
    for (const b of draft) {
      const key = b.key.trim().toUpperCase();
      const score = parseFloat(b.min_score);
      if (!key) { setError('Band names cannot be empty.'); return; }
      if (Number.isNaN(score) || score <= 0 || score > 1) { setError(`${key || 'A band'} score must be between 0 and 1.`); return; }
      if (!/^#[0-9A-Fa-f]{6}$/.test(b.color)) { setError(`${key} has an invalid color.`); return; }
      parsed.push({ key, min_score: score, color: b.color });
    }

    const keys = parsed.map((b) => b.key);
    if (new Set(keys).size !== keys.length) { setError('Band names must be unique.'); return; }
    const scores = parsed.map((b) => b.min_score);
    if (new Set(scores).size !== scores.length) { setError('Band scores must be unique.'); return; }

    setSaving(true);
    try {
      const res: any = await updateRiskBands(parsed);
      const toDraft = (b: any[]) => b.map((x) => ({ key: x.key, min_score: String(x.min_score), color: x.color }));
      setDraft(toDraft(res.bands));
      useRiskConfigStore.getState().setBands(res.bands);
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save bands.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        id="risk_config_panel"
        onClick={(e) => e.stopPropagation()}
        className="w-[460px] max-h-[80vh] overflow-y-auto bg-[#060a15] border border-cyan-800/30 rounded-lg shadow-[0_0_30px_rgba(6,182,212,0.1)] font-mono"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#141d33]/60 sticky top-0 bg-[#060a15] z-10">
          <span className="text-[11px] font-extrabold text-cyan-400 uppercase tracking-wider">
            Risk Category Configuration
          </span>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-2">
          {loading ? (
            <div className="text-[10px] text-slate-500 uppercase text-center py-6">Loading…</div>
          ) : (
            <>
              <div className="flex items-center gap-2 text-[8px] text-slate-500 uppercase font-bold pb-1">
                <span className="w-2.5" />
                <span className="flex-1">Name</span>
                <span className="w-20 text-right">Min score</span>
                <span className="w-12 text-center">Color</span>
                <span className="w-6" />
              </div>

              {draft.map((band, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: /^#[0-9A-Fa-f]{6}$/.test(band.color) ? band.color : '#666' }}
                  />
                  <input
                    id={`risk_band_key_${idx}`}
                    type="text"
                    value={band.key}
                    onChange={(e) => handleFieldChange(idx, 'key', e.target.value)}
                    maxLength={24}
                    className="flex-1 min-w-0 px-2 py-1 bg-[#0a0f1e] border border-cyan-800/30 rounded text-[11px] text-slate-200 uppercase focus:outline-none focus:border-cyan-500/60"
                  />
                  <input
                    id={`risk_band_score_${idx}`}
                    type="number"
                    step="0.001"
                    min="0"
                    max="1"
                    value={band.min_score}
                    onChange={(e) => handleFieldChange(idx, 'min_score', e.target.value)}
                    className="w-20 px-2 py-1 bg-[#0a0f1e] border border-cyan-800/30 rounded text-[11px] text-cyan-300 text-right focus:outline-none focus:border-cyan-500/60"
                  />
                  <input
                    id={`risk_band_color_${idx}`}
                    type="color"
                    value={/^#[0-9A-Fa-f]{6}$/.test(band.color) ? band.color : '#666666'}
                    onChange={(e) => handleFieldChange(idx, 'color', e.target.value)}
                    className="w-12 h-7 bg-[#0a0f1e] border border-cyan-800/30 rounded cursor-pointer"
                  />
                  <button
                    id={`btn_remove_band_${idx}`}
                    onClick={() => handleRemoveBand(idx)}
                    disabled={draft.length <= minBands}
                    className={`w-6 shrink-0 flex items-center justify-center ${draft.length <= minBands ? 'text-slate-700 cursor-not-allowed' : 'text-slate-500 hover:text-[#FF2D55] cursor-pointer'}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}

              <button
                id="btn_add_band"
                onClick={handleAddBand}
                disabled={draft.length >= maxBands}
                className={`w-full mt-2 flex items-center justify-center gap-1.5 py-1.5 rounded border border-dashed text-[9px] uppercase font-bold ${
                  draft.length >= maxBands
                    ? 'opacity-40 cursor-not-allowed border-cyan-800/20 text-slate-500'
                    : 'border-cyan-800/40 text-cyan-400 hover:bg-cyan-500/10 cursor-pointer'
                }`}
              >
                <Plus className="w-3 h-3" />
                Add band ({draft.length}/{maxBands})
              </button>

              {error && (
                <div className="text-[9px] text-[#FF6B35] bg-[#FF2D55]/10 border border-[#FF2D55]/30 rounded px-2 py-1.5 mt-2">
                  {error}
                </div>
              )}
              {savedMsg && (
                <div className="text-[9px] text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 rounded px-2 py-1.5 mt-2">
                  Bands updated — applied on next sweep.
                </div>
              )}
            </>
          )}
        </div>

        {!loading && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#141d33]/60 sticky bottom-0 bg-[#060a15]">
            <button
              id="btn_reset_risk_defaults"
              onClick={handleResetDefaults}
              className="flex items-center gap-1.5 text-[9px] text-slate-500 hover:text-slate-300 uppercase font-bold cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" />
              Reset to defaults
            </button>
            <button
              id="btn_save_risk_thresholds"
              onClick={handleSave}
              disabled={saving}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded border font-bold text-[9px] uppercase transition-all ${
                saving
                  ? 'opacity-40 cursor-not-allowed border-cyan-800/20 text-slate-500'
                  : 'border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/10 cursor-pointer'
              }`}
            >
              <Save className="w-3 h-3" />
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}