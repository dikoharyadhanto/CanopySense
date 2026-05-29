import { useState, useRef } from 'react';
import {
  listCompanies,
  listOnboardingEstates,
  createOnboardingEstate,
  getOnboardingEstateDetail,
  editOnboardingEstate,
  previewImport,
  commitImport,
  Company,
  EstateStub,
  EstateDetail,
  ImportPreviewResult,
} from '../../lib/adminApi';

type Step = 'company' | 'estate' | 'upload' | 'preview' | 'commit';

export default function EstateOnboarding() {
  const [step, setStep] = useState<Step>('company');

  // Company selection
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  const [companiesLoaded, setCompaniesLoaded] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);

  // Estate list + selection
  const [estates, setEstates] = useState<EstateStub[]>([]);
  const [estatesLoading, setEstatesLoading] = useState(false);
  const [selectedEstate, setSelectedEstate] = useState<EstateStub | null>(null);
  const [estateDetail, setEstateDetail] = useState<EstateDetail | null>(null);

  // Create estate form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCode, setNewCode] = useState('');
  const [createError, setCreateError] = useState('');
  const [createLoading, setCreateLoading] = useState(false);

  // Edit estate
  const [showEditForm, setShowEditForm] = useState(false);
  const [editName, setEditName] = useState('');
  const [editCode, setEditCode] = useState('');
  const [editError, setEditError] = useState('');
  const [editLoading, setEditLoading] = useState(false);

  // File upload + preview
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState<ImportPreviewResult | null>(null);
  const [previewError, setPreviewError] = useState('');

  // Commit
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitResult, setCommitResult] = useState<{
    estate_id: number; afdelings_created: number; blocks_created: number
  } | null>(null);
  const [commitError, setCommitError] = useState('');

  const [globalError, setGlobalError] = useState('');

  // ── Step 1: Load + select company ──────────────────────────────────────
  async function loadCompanies() {
    if (companiesLoaded) return;
    setCompaniesLoading(true);
    setGlobalError('');
    try {
      const data = await listCompanies({ limit: 200 });
      setCompanies(data.items);
      setCompaniesLoaded(true);
    } catch {
      setGlobalError('Failed to load companies.');
    } finally {
      setCompaniesLoading(false);
    }
  }

  function selectCompany(company: Company) {
    setSelectedCompany(company);
    setEstates([]);
    setSelectedEstate(null);
    setEstateDetail(null);
    setStep('estate');
    loadEstates(company.id);
  }

  // ── Step 2: Load + select or create estate ──────────────────────────────
  async function loadEstates(companyId: number) {
    setEstatesLoading(true);
    setGlobalError('');
    try {
      const items = await listOnboardingEstates(companyId);
      setEstates(items);
    } catch {
      setGlobalError('Failed to load estates.');
    } finally {
      setEstatesLoading(false);
    }
  }

  async function handleCreateEstate() {
    if (!selectedCompany) return;
    setCreateLoading(true);
    setCreateError('');
    try {
      const created = await createOnboardingEstate(selectedCompany.id, {
        name: newName,
        code: newCode,
      });
      setEstates((prev) => [created, ...prev]);
      setShowCreateForm(false);
      setNewName('');
      setNewCode('');
      selectEstate(created);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setCreateError(typeof msg === 'string' ? msg : 'Failed to create estate.');
    } finally {
      setCreateLoading(false);
    }
  }

  async function selectEstate(estate: EstateStub) {
    setSelectedEstate(estate);
    setPreviewResult(null);
    setCommitResult(null);
    setCommitError('');
    setPreviewError('');
    setGlobalError('');
    try {
      const detail = await getOnboardingEstateDetail(estate.id);
      setEstateDetail(detail);
    } catch {
      // non-fatal
    }
    setStep('upload');
  }

  async function handleEditEstate() {
    if (!selectedEstate) return;
    setEditLoading(true);
    setEditError('');
    try {
      const updated = await editOnboardingEstate(selectedEstate.id, {
        name: editName || undefined,
        code: editCode || undefined,
      });
      setSelectedEstate(updated);
      setEstates((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
      setShowEditForm(false);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setEditError(typeof msg === 'string' ? msg : 'Failed to update estate.');
    } finally {
      setEditLoading(false);
    }
  }

  // ── Step 3: Upload + preview ────────────────────────────────────────────
  async function handlePreview() {
    if (!selectedEstate || !selectedFile) return;
    setPreviewLoading(true);
    setPreviewError('');
    setPreviewResult(null);
    try {
      const result = await previewImport(selectedEstate.id, selectedFile);
      setPreviewResult(result);
      setStep('preview');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setPreviewError(typeof detail === 'string' ? detail : 'Preview failed.');
    } finally {
      setPreviewLoading(false);
    }
  }

  // ── Step 4: Commit ──────────────────────────────────────────────────────
  async function handleCommit() {
    if (!selectedEstate || !selectedFile) return;
    setCommitLoading(true);
    setCommitError('');
    try {
      const result = await commitImport(selectedEstate.id, selectedFile);
      setCommitResult(result);
      setStep('commit');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : typeof detail === 'object' && detail !== null
          ? (detail as { message?: string }).message ?? 'Commit failed.'
          : 'Commit failed.';
      setCommitError(msg);
    } finally {
      setCommitLoading(false);
    }
  }

  function resetToEstateList() {
    setStep('estate');
    setSelectedFile(null);
    setPreviewResult(null);
    setCommitResult(null);
    setCommitError('');
    setPreviewError('');
    if (fileRef.current) fileRef.current.value = '';
    if (selectedCompany) loadEstates(selectedCompany.id);
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-xl font-bold text-slate-800 mb-1">Estate Onboarding</h1>
        <p className="text-sm text-slate-500 mb-6">
          Create estate metadata stubs and import block boundaries from GeoJSON.
        </p>

        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-400 mb-6">
          <button
            onClick={() => { setStep('company'); loadCompanies(); }}
            className="hover:text-slate-700 transition-colors"
          >
            Companies
          </button>
          {selectedCompany && (
            <>
              <span>/</span>
              <button
                onClick={() => setStep('estate')}
                className="hover:text-slate-700 transition-colors"
              >
                {selectedCompany.company_name}
              </button>
            </>
          )}
          {selectedEstate && step !== 'estate' && (
            <>
              <span>/</span>
              <span className="text-slate-600">{selectedEstate.name}</span>
            </>
          )}
        </div>

        {globalError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-md">
            {globalError}
          </div>
        )}

        {/* ── Step: company ─────────────────────────────────────────── */}
        {step === 'company' && (
          <div className="bg-white border border-slate-200 rounded-lg p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">Select a company</h2>
            {!companiesLoaded ? (
              <button
                onClick={loadCompanies}
                disabled={companiesLoading}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {companiesLoading ? 'Loading…' : 'Load companies'}
              </button>
            ) : (
              <div className="space-y-2">
                {companies.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => selectCompany(c)}
                    className="w-full text-left px-4 py-3 border border-slate-200 rounded-md hover:border-indigo-400 hover:bg-indigo-50 transition-colors"
                  >
                    <div className="text-sm font-medium text-slate-800">{c.company_name}</div>
                    <div className="text-xs text-slate-400">{c.company_id}</div>
                  </button>
                ))}
                {companies.length === 0 && (
                  <p className="text-sm text-slate-500">No companies found.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Step: estate ──────────────────────────────────────────── */}
        {step === 'estate' && selectedCompany && (
          <div className="bg-white border border-slate-200 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-slate-700">
                Estates — {selectedCompany.company_name}
              </h2>
              <button
                onClick={() => { setShowCreateForm(true); setCreateError(''); setNewName(''); setNewCode(''); }}
                className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-md hover:bg-indigo-700"
              >
                + New estate
              </button>
            </div>

            {showCreateForm && (
              <div className="mb-4 p-4 bg-slate-50 border border-slate-200 rounded-md">
                <div className="text-xs font-semibold text-slate-700 mb-3">Create estate stub</div>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Estate name</label>
                    <input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="e.g. Sumbawa Estate"
                      className="w-full text-sm border border-slate-300 rounded px-3 py-1.5 focus:outline-none focus:border-indigo-400"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Estate code (max 20 chars)</label>
                    <input
                      value={newCode}
                      onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                      placeholder="e.g. SMB-EST-01"
                      maxLength={20}
                      className="w-full text-sm border border-slate-300 rounded px-3 py-1.5 focus:outline-none focus:border-indigo-400 font-mono"
                    />
                  </div>
                </div>
                {createError && (
                  <p className="text-xs text-red-600 mb-2">{createError}</p>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={handleCreateEstate}
                    disabled={createLoading || !newName.trim() || !newCode.trim()}
                    className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-md hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {createLoading ? 'Creating…' : 'Create'}
                  </button>
                  <button
                    onClick={() => setShowCreateForm(false)}
                    className="px-3 py-1.5 text-slate-600 text-xs rounded-md border border-slate-300 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {estatesLoading ? (
              <p className="text-sm text-slate-500">Loading estates…</p>
            ) : (
              <div className="space-y-2">
                {estates.map((e) => (
                  <button
                    key={e.id}
                    onClick={() => selectEstate(e)}
                    className="w-full text-left px-4 py-3 border border-slate-200 rounded-md hover:border-indigo-400 hover:bg-indigo-50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm font-medium text-slate-800">{e.name}</span>
                        <span className="ml-2 text-xs text-slate-400 font-mono">{e.code}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {e.is_draft && (
                          <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-[10px] rounded-full font-semibold">
                            DRAFT
                          </span>
                        )}
                        <span className="text-xs text-slate-400">
                          {e.block_count} blocks
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
                {estates.length === 0 && !showCreateForm && (
                  <p className="text-sm text-slate-500">No estates yet. Create one above.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Step: upload ──────────────────────────────────────────── */}
        {step === 'upload' && selectedEstate && (
          <div className="space-y-4">
            {/* Estate header */}
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-base font-semibold text-slate-800">{selectedEstate.name}</div>
                  <div className="text-xs text-slate-400 font-mono mt-0.5">{selectedEstate.code}</div>
                  {estateDetail && (
                    <div className="text-xs text-slate-500 mt-1">
                      {estateDetail.afdeling_count} afdelings · {estateDetail.block_count} blocks
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {selectedEstate.is_draft && (
                    <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-[10px] rounded-full font-semibold">
                      DRAFT
                    </span>
                  )}
                  {selectedEstate.is_draft && (
                    <button
                      onClick={() => {
                        setEditName(selectedEstate.name);
                        setEditCode(selectedEstate.code);
                        setEditError('');
                        setShowEditForm(true);
                      }}
                      className="text-xs text-indigo-600 hover:text-indigo-800"
                    >
                      Edit metadata
                    </button>
                  )}
                </div>
              </div>

              {showEditForm && (
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Name</label>
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="w-full text-sm border border-slate-300 rounded px-3 py-1.5 focus:outline-none focus:border-indigo-400"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Code</label>
                      <input
                        value={editCode}
                        onChange={(e) => setEditCode(e.target.value.toUpperCase())}
                        maxLength={20}
                        className="w-full text-sm border border-slate-300 rounded px-3 py-1.5 focus:outline-none focus:border-indigo-400 font-mono"
                      />
                    </div>
                  </div>
                  {editError && <p className="text-xs text-red-600 mb-2">{editError}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={handleEditEstate}
                      disabled={editLoading}
                      className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-md hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {editLoading ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      onClick={() => setShowEditForm(false)}
                      className="px-3 py-1.5 text-slate-600 text-xs rounded-md border border-slate-300 hover:bg-slate-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* File upload */}
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Upload block boundaries</h3>
              <p className="text-xs text-slate-500 mb-4">
                GeoJSON FeatureCollection of Polygon features. Each feature must include
                block_code, block_name, afdeling_code, afdeling_name properties.
                Max 10 MB.
              </p>

              <input
                ref={fileRef}
                type="file"
                accept=".geojson,.json"
                onChange={(e) => {
                  setSelectedFile(e.target.files?.[0] ?? null);
                  setPreviewResult(null);
                  setPreviewError('');
                }}
                className="block text-sm text-slate-600 mb-4
                  file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0
                  file:text-xs file:font-medium file:bg-indigo-50 file:text-indigo-700
                  hover:file:bg-indigo-100"
              />

              {previewError && (
                <div className="mb-3 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-md">
                  {previewError}
                </div>
              )}

              <button
                onClick={handlePreview}
                disabled={!selectedFile || previewLoading}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {previewLoading ? 'Validating…' : 'Validate & preview'}
              </button>
            </div>
          </div>
        )}

        {/* ── Step: preview ─────────────────────────────────────────── */}
        {step === 'preview' && previewResult && selectedEstate && (
          <div className="space-y-4">
            {/* Result summary */}
            <div className={`border rounded-lg p-5 ${
              previewResult.commit_eligible
                ? 'bg-green-50 border-green-200'
                : 'bg-red-50 border-red-200'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-sm font-bold ${
                  previewResult.commit_eligible ? 'text-green-800' : 'text-red-800'
                }`}>
                  {previewResult.commit_eligible ? 'Ready to commit' : 'Not eligible — fix errors first'}
                </span>
              </div>
              {previewResult.file_error && (
                <p className="text-sm text-red-700">{previewResult.file_error}</p>
              )}
              {!previewResult.file_error && (
                <div className="text-xs text-slate-600 space-y-0.5">
                  <div>{previewResult.valid_blocks.length} valid blocks</div>
                  <div>{previewResult.afdeling_count} afdelings</div>
                  {previewResult.invalid_rows.length > 0 && (
                    <div className="text-red-700">{previewResult.invalid_rows.length} invalid rows</div>
                  )}
                </div>
              )}
            </div>

            {previewResult.warnings.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-md space-y-1">
                {previewResult.warnings.map((w, i) => <div key={i}>{w}</div>)}
              </div>
            )}

            {/* Invalid rows */}
            {previewResult.invalid_rows.length > 0 && (
              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-100 bg-red-50">
                  <h3 className="text-xs font-semibold text-red-700">
                    Invalid rows ({previewResult.invalid_rows.length})
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50 border-b border-slate-100">
                      <tr>
                        <th className="text-left px-4 py-2 text-slate-500 font-medium">Row</th>
                        <th className="text-left px-4 py-2 text-slate-500 font-medium">block_code</th>
                        <th className="text-left px-4 py-2 text-slate-500 font-medium">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewResult.invalid_rows.map((row, i) => (
                        <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                          <td className="px-4 py-2 text-slate-500">{row.index}</td>
                          <td className="px-4 py-2 font-mono text-slate-700">{row.block_code ?? '—'}</td>
                          <td className="px-4 py-2 text-red-600">{row.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Valid blocks preview */}
            {previewResult.valid_blocks.length > 0 && (
              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-100 bg-green-50">
                  <h3 className="text-xs font-semibold text-green-700">
                    Valid blocks ({previewResult.valid_blocks.length})
                  </h3>
                </div>
                <div className="overflow-x-auto max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50 border-b border-slate-100 sticky top-0">
                      <tr>
                        <th className="text-left px-4 py-2 text-slate-500 font-medium">block_code</th>
                        <th className="text-left px-4 py-2 text-slate-500 font-medium">block_name</th>
                        <th className="text-left px-4 py-2 text-slate-500 font-medium">afdeling_code</th>
                        <th className="text-left px-4 py-2 text-slate-500 font-medium">plant_year</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewResult.valid_blocks.map((b, i) => (
                        <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                          <td className="px-4 py-2 font-mono text-slate-700">{b.block_code}</td>
                          <td className="px-4 py-2 text-slate-700">{b.block_name}</td>
                          <td className="px-4 py-2 font-mono text-slate-500">{b.afdeling_code}</td>
                          <td className="px-4 py-2 text-slate-500">{b.plant_year ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center gap-3">
              {previewResult.commit_eligible && (
                <button
                  onClick={handleCommit}
                  disabled={commitLoading}
                  className="px-5 py-2 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 disabled:opacity-50 font-semibold"
                >
                  {commitLoading ? 'Committing…' : 'Commit import'}
                </button>
              )}
              <button
                onClick={() => setStep('upload')}
                className="px-4 py-2 text-slate-600 text-sm border border-slate-300 rounded-md hover:bg-slate-50"
              >
                Back
              </button>
            </div>

            {commitError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-md">
                {commitError}
              </div>
            )}
          </div>
        )}

        {/* ── Step: commit success ───────────────────────────────────── */}
        {step === 'commit' && commitResult && (
          <div className="bg-white border border-green-200 rounded-lg p-6">
            <div className="text-base font-bold text-green-800 mb-2">Import committed</div>
            <div className="text-sm text-slate-600 space-y-1">
              <div>Estate ID: <span className="font-mono">{commitResult.estate_id}</span></div>
              <div>Afdelings created: <span className="font-semibold">{commitResult.afdelings_created}</span></div>
              <div>Blocks inserted: <span className="font-semibold">{commitResult.blocks_created}</span></div>
            </div>
            <button
              onClick={resetToEstateList}
              className="mt-4 px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
            >
              Back to estates
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
