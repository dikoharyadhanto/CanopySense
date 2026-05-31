import { useTranslation } from 'react-i18next';

const INDICES = [
  { value: 'ndvi', label: 'NDVI' },
  { value: 'evi', label: 'EVI' },
  { value: 'ndre', label: 'NDRE' },
  { value: 'savi', label: 'SAVI' },
  { value: 'gndvi', label: 'GNDVI' },
] as const;

export type IndexKey = typeof INDICES[number]['value'];

interface Props {
  value: IndexKey;
  onChange: (v: IndexKey) => void;
}

export default function IndexSelector({ value, onChange }: Props) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2">
      <label className="text-sm font-medium text-gray-700 whitespace-nowrap">{t('indexSelector.label')}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as IndexKey)}
        className="text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        {INDICES.map((idx) => (
          <option key={idx.value} value={idx.value}>{idx.label}</option>
        ))}
      </select>
    </div>
  );
}
