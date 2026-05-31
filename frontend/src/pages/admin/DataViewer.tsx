import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';
import {
  getDataViewerCatalog,
  getDataViewerColumns,
  getDataViewerRows,
  type DataViewerTable,
  type DataViewerColumnMeta,
  type DataViewerRowsResponse,
} from '../../lib/adminApi';

const PAGE_SIZE = 20;

export default function DataViewer() {
  const { t } = useTranslation();
  const [tables, setTables] = useState<DataViewerTable[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string>('');
  const [columnMeta, setColumnMeta] = useState<DataViewerColumnMeta | null>(null);
  const [rowsData, setRowsData] = useState<DataViewerRowsResponse | null>(null);

  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState('');
  const [sortDir, setSortDir] = useState<'ASC' | 'DESC'>('DESC');
  const [filterVal, setFilterVal] = useState('');
  const [pendingFilter, setPendingFilter] = useState('');

  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [loadingRows, setLoadingRows] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDataViewerCatalog()
      .then((data) => {
        setTables(data.tables);
        setLoadingCatalog(false);
      })
      .catch(() => {
        setError('Failed to load table catalog.');
        setLoadingCatalog(false);
      });
  }, []);

  useEffect(() => {
    if (!selectedTableId) return;
    setColumnMeta(null);
    setRowsData(null);
    setPage(1);
    setSortCol('');
    setSortDir('DESC');
    setFilterVal('');
    setPendingFilter('');
    setError(null);

    getDataViewerColumns(selectedTableId)
      .then(setColumnMeta)
      .catch(() => setError('Failed to load column metadata.'));
  }, [selectedTableId]);

  useEffect(() => {
    if (!selectedTableId || !columnMeta) return;
    setLoadingRows(true);
    setError(null);
    getDataViewerRows(selectedTableId, {
      page,
      page_size: PAGE_SIZE,
      sort_col: sortCol,
      sort_dir: sortDir,
      filter_col: filterVal && columnMeta.search_col ? columnMeta.search_col : '',
      filter_val: filterVal,
    })
      .then((data) => {
        setRowsData(data);
        setLoadingRows(false);
      })
      .catch(() => {
        setError('Failed to load rows.');
        setLoadingRows(false);
      });
  }, [selectedTableId, columnMeta, page, sortCol, sortDir, filterVal]);

  function handleTableSelect(tableId: string) {
    setSelectedTableId(tableId);
  }

  function handleSort(col: string) {
    if (!columnMeta?.sort_allowed.includes(col)) return;
    if (sortCol === col) {
      setSortDir((d) => (d === 'DESC' ? 'ASC' : 'DESC'));
    } else {
      setSortCol(col);
      setSortDir('DESC');
    }
    setPage(1);
  }

  function handleFilterSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFilterVal(pendingFilter);
    setPage(1);
  }

  function handleFilterClear() {
    setPendingFilter('');
    setFilterVal('');
    setPage(1);
  }

  const totalPages = rowsData ? Math.max(1, Math.ceil(rowsData.total / PAGE_SIZE)) : 1;

  function formatCellValue(val: unknown): string {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'boolean') return val ? 'true' : 'false';
    const s = String(val);
    return s.length > 120 ? s.slice(0, 120) + '…' : s;
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-slate-200 bg-white">
        <h1 className="text-lg font-semibold text-slate-800">{t('admin.dataViewer.title')}</h1>
        <p className="text-xs text-slate-500 mt-0.5">{t('admin.dataViewer.subtitle')}</p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar: table selector */}
        <aside className="w-48 flex-shrink-0 border-r border-slate-200 bg-slate-50 overflow-y-auto">
          <div className="px-3 pt-3 pb-1">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Tables
            </div>
          </div>
          {loadingCatalog ? (
            <div className="px-3 py-4 text-xs text-slate-400">Loading…</div>
          ) : tables.length === 0 ? (
            <div className="px-3 py-4 text-xs text-slate-400">No tables available.</div>
          ) : (
            <ul className="py-1">
              {tables.map((t) => (
                <li key={t.id}>
                  <button
                    onClick={() => handleTableSelect(t.id)}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                      selectedTableId === t.id
                        ? 'bg-indigo-100 text-indigo-800 font-semibold'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <div className="font-medium truncate">{t.display}</div>
                    <div className="text-[10px] text-slate-400 truncate">{t.schema}.{t.table}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Main panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!selectedTableId ? (
            <div className="flex-1 flex items-center justify-center text-sm text-slate-400">
              Select a table from the list to inspect its data.
            </div>
          ) : (
            <>
              {/* Toolbar */}
              <div className="flex-shrink-0 px-4 py-2 border-b border-slate-200 bg-white flex items-center gap-3 flex-wrap">
                <span className="text-sm font-semibold text-slate-700">
                  {columnMeta?.display ?? selectedTableId}
                </span>
                {rowsData && (
                  <span className="text-xs text-slate-400">
                    {rowsData.total.toLocaleString()} row{rowsData.total !== 1 ? 's' : ''}
                  </span>
                )}
                <div className="flex-1" />
                {/* Filter */}
                {columnMeta?.search_col && (
                  <form onSubmit={handleFilterSubmit} className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={pendingFilter}
                      onChange={(e) => setPendingFilter(e.target.value)}
                      placeholder={`Search ${columnMeta.search_col}…`}
                      className="text-xs border border-slate-200 rounded px-2 py-1 w-44 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                    <button
                      type="submit"
                      className="text-xs px-2 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700"
                    >
                      Go
                    </button>
                    {filterVal && (
                      <button
                        type="button"
                        onClick={handleFilterClear}
                        className="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded hover:bg-slate-200"
                      >
                        Clear
                      </button>
                    )}
                  </form>
                )}
              </div>

              {/* Error */}
              {error && (
                <div className="flex-shrink-0 px-4 py-2 bg-red-50 border-b border-red-100 text-xs text-red-600">
                  {error}
                </div>
              )}

              {/* Table */}
              <div className="flex-1 overflow-auto">
                {loadingRows || !rowsData ? (
                  <div className="flex items-center justify-center h-32 text-sm text-slate-400">
                    {loadingRows ? 'Loading…' : 'Select a table to view data.'}
                  </div>
                ) : rowsData.rows.length === 0 ? (
                  <div className="flex items-center justify-center h-32 text-sm text-slate-400">
                    No rows found.
                  </div>
                ) : (
                  <table className="min-w-full text-xs border-collapse">
                    <thead className="bg-slate-100 sticky top-0 z-10">
                      <tr>
                        {rowsData.columns.map((col) => {
                          const sortable = columnMeta?.sort_allowed.includes(col);
                          const isActive = sortCol === col;
                          return (
                            <th
                              key={col}
                              onClick={() => sortable && handleSort(col)}
                              className={`px-3 py-2 text-left font-semibold text-slate-600 whitespace-nowrap border-b border-slate-200 select-none ${
                                sortable ? 'cursor-pointer hover:bg-slate-200' : ''
                              } ${isActive ? 'text-indigo-700' : ''}`}
                            >
                              {col}
                              {isActive && (
                                <span className="ml-1 text-indigo-500">
                                  {sortDir === 'DESC' ? '↓' : '↑'}
                                </span>
                              )}
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {rowsData.rows.map((row, ri) => (
                        <tr
                          key={ri}
                          className={ri % 2 === 0 ? 'bg-white' : 'bg-slate-50/60'}
                        >
                          {rowsData.columns.map((col) => (
                            <td
                              key={col}
                              className="px-3 py-1.5 text-slate-700 border-b border-slate-100 max-w-xs truncate"
                              title={String(row[col] ?? '')}
                            >
                              {formatCellValue(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Pagination */}
              {rowsData && rowsData.total > 0 && (
                <div className="flex-shrink-0 px-4 py-2 border-t border-slate-200 bg-white flex items-center gap-3 text-xs text-slate-600">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="px-2 py-1 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
                  >
                    ← Prev
                  </button>
                  <span>
                    Page {page} of {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="px-2 py-1 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
                  >
                    Next →
                  </button>
                  <span className="ml-auto text-slate-400">
                    {rowsData.total.toLocaleString()} total rows · max {PAGE_SIZE}/page
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
