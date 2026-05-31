import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { createManager } from '../../lib/adminApi';

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      onClick={handleCopy}
      className="mt-2 px-3 py-1.5 text-xs bg-amber-100 hover:bg-amber-200 text-amber-800 border border-amber-300 rounded transition-colors font-medium"
    >
      {copied ? 'Tersalin!' : 'Salin Token'}
    </button>
  );
}

export default function ManagerInvite() {
  const { t } = useTranslation();
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ token: string; expires_at: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await createManager({
        email,
        company_id: Number(companyId),
      });
      setResult({ token: res.setup_token, expires_at: res.setup_token_expires_at });
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to invite manager');
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="text-xl font-bold text-slate-800 mb-4">Manager Invited</h1>
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-5 max-w-lg">
          <p className="text-sm font-semibold text-amber-800 mb-2">
            Setup token — shown only once
          </p>
          <p className="text-xs text-amber-700 mb-4">
            Copy this token and send it to the manager securely. It expires at{' '}
            <strong>{new Date(result.expires_at).toLocaleString()}</strong>.
            It will not be shown again. The manager sets their own name and username at first login.
          </p>
          <div className="bg-white border border-amber-200 rounded p-3 font-mono text-sm break-all select-all">
            {result.token}
          </div>
          <CopyButton text={result.token} />
          <button
            onClick={() => navigate(`/admin/companies/${companyId}`)}
            className="mt-4 px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
          >
            Done — Back to Company
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <button
        onClick={() => navigate(`/admin/companies/${companyId}`)}
        className="text-sm text-indigo-600 hover:text-indigo-800 mb-4 inline-block"
      >
        ← Back to Company
      </button>
      <h1 className="text-xl font-bold text-slate-800 mb-6">{t('navigation.admin.adminUsers')}</h1>
      <p className="text-sm text-slate-500 mb-4">
        Enter the manager's email. They will set their own name, username, and password using the
        setup token shown after creation.
      </p>
      <form onSubmit={handleSubmit} className="max-w-md space-y-4">
        <div>
          <label className="block text-sm text-slate-600 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? 'Inviting...' : 'Invite Manager'}
        </button>
      </form>
    </div>
  );
}
