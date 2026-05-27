import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts';

export interface IndexRow {
  acquisition_date: string;
  ndvi: number | null;
  evi: number | null;
  ndre: number | null;
  savi: number | null;
  gndvi: number | null;
  cloud_cover: number | null;
  sensor: string;
}

interface Props {
  data: IndexRow[];
  showEvi: boolean;
  showNdre: boolean;
  showSavi: boolean;
  showGndvi: boolean;
}

const CLOUD_THRESHOLD = 30;

function formatDate(d: string) {
  return d.slice(0, 10);
}

export default function TimeSeriesChart({ data, showEvi, showNdre, showSavi, showGndvi }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Tidak ada data untuk blok ini.
      </div>
    );
  }

  const highCloudDates = data
    .filter((r) => r.cloud_cover !== null && r.cloud_cover > CLOUD_THRESHOLD)
    .map((r) => r.acquisition_date);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="acquisition_date"
          tickFormatter={formatDate}
          tick={{ fontSize: 11 }}
          angle={-30}
          textAnchor="end"
          height={48}
        />
        <YAxis domain={[-1, 1]} tick={{ fontSize: 11 }} tickCount={9} />
        <Tooltip
          formatter={(value) => (typeof value === 'number' ? value.toFixed(4) : 'N/A')}
          labelFormatter={(label) => `Tanggal: ${label}`}
        />
        <Legend />

        {highCloudDates.map((d) => (
          <ReferenceLine
            key={d}
            x={d}
            stroke="#f87171"
            strokeDasharray="4 2"
            strokeWidth={1}
          />
        ))}

        <Line
          type="monotone"
          dataKey="ndvi"
          stroke="#16a34a"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
          name="NDVI"
        />
        {showEvi && (
          <Line
            type="monotone"
            dataKey="evi"
            stroke="#2563eb"
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
            name="EVI"
          />
        )}
        {showNdre && (
          <Line
            type="monotone"
            dataKey="ndre"
            stroke="#d97706"
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
            name="NDRE"
          />
        )}
        {showSavi && (
          <Line
            type="monotone"
            dataKey="savi"
            stroke="#9333ea"
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
            name="SAVI"
          />
        )}
        {showGndvi && (
          <Line
            type="monotone"
            dataKey="gndvi"
            stroke="#0d9488"
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
            name="GNDVI"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
