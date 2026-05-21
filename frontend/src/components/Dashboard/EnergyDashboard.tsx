import { useState, useEffect, useCallback } from 'react';
import { Zap, Activity, Thermometer, Hash, Gauge } from 'lucide-react';
import { fetchEnergy, fetchTelemetry } from '../../lib/api';
import { useAppStore } from '../../lib/store';

interface EnergySample {
  timestamp: string;
  power_w: number;
  energy_j: number;
}

interface EnergyData {
  total_energy_j?: number;
  energy_per_token_j?: number;
  avg_power_w?: number;
  samples?: EnergySample[];
}

interface TelemetryStats {
  total_requests?: number;
  total_tokens?: number;
}

interface ChartPoint {
  time: string;
  power: number;
}

function StatCard({
  icon: Icon,
  label,
  value,
  unit,
}: {
  icon: typeof Zap;
  label: string;
  value: string;
  unit?: string;
}) {
  return (
    <div className="hud-panel p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={12} style={{ color: 'var(--color-accent)' }} />
        <span className="hud-label">{label}</span>
      </div>
      <div className="hud-mono text-2xl font-semibold truncate" style={{ color: 'var(--color-text)' }}>
        {value}
        {unit && (
          <span className="hud-label ml-1" style={{ fontSize: '0.625rem', letterSpacing: '0.18em' }}>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}

function PowerLineChart({ data }: { data: ChartPoint[] }) {
  const width = 480;
  const height = 180;
  const padding = { top: 12, right: 16, bottom: 26, left: 40 };
  const values = data.map((point) => point.power);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const points = data.map((point, index) => {
    const x = padding.left + (index / Math.max(data.length - 1, 1)) * innerWidth;
    const y = padding.top + (1 - (point.power - min) / range) * innerHeight;
    return { ...point, x, y };
  });
  const path = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(' ');

  return (
    <svg className="h-full w-full overflow-visible" viewBox={`0 0 ${width} ${height}`} role="img">
      <title>Power draw over time</title>
      {[0, 1, 2, 3].map((step) => {
        const y = padding.top + (step / 3) * innerHeight;
        const value = max - (step / 3) * range;
        return (
          <g key={step}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="var(--color-border)" strokeDasharray="3 3" />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--color-text-tertiary)">
              {value.toFixed(0)}W
            </text>
          </g>
        );
      })}
      <path d={path} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((point, index) => (
        <circle key={`${point.time}-${index}`} cx={point.x} cy={point.y} r="2.5" fill="var(--color-accent)">
          <title>{`${point.time}: ${point.power.toFixed(1)}W`}</title>
        </circle>
      ))}
      <text x={padding.left} y={height - 6} fontSize="10" fill="var(--color-text-tertiary)">
        {data[0]?.time}
      </text>
      <text x={width - padding.right} y={height - 6} textAnchor="end" fontSize="10" fill="var(--color-text-tertiary)">
        {data[data.length - 1]?.time}
      </text>
    </svg>
  );
}

export function EnergyDashboard() {
  const savings = useAppStore((s) => s.savings);
  const [energy, setEnergy] = useState<EnergyData | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryStats | null>(null);
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [energyRes, telRes] = await Promise.allSettled([
        fetchEnergy().catch(() => null),
        fetchTelemetry().catch(() => null),
      ]);

      if (energyRes.status === 'fulfilled' && energyRes.value) {
        const data = energyRes.value as EnergyData;
        setEnergy(data);
        if (data.samples) {
          setChartData(
            data.samples.map((s) => ({
              time: new Date(s.timestamp).toLocaleTimeString(),
              power: Math.round(s.power_w * 10) / 10,
            })),
          );
        }
        setError(null);
      }
      if (telRes.status === 'fulfilled' && telRes.value) {
        setTelemetry(telRes.value as TelemetryStats);
      }
    } catch {
      setError('Cannot connect to server');
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const thermalStatus = (energy?.avg_power_w ?? 0) < 50
    ? { label: 'Cool', color: 'var(--color-success)' }
    : (energy?.avg_power_w ?? 0) < 150
    ? { label: 'Warm', color: 'var(--color-warning)' }
    : { label: 'Hot', color: 'var(--color-error)' };

  if (error || !energy) {
    return (
      <div className="hud-panel p-6">
        <h3 className="hud-label flex items-center gap-2 mb-4">
          <Zap size={12} style={{ color: 'var(--color-accent)' }} />
          Energy Monitoring
        </h3>
        <div className="h-48 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          <span className="hud-mono">{error || 'awaiting telemetry stream…'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="hud-panel p-6">
      <h3 className="hud-label flex items-center gap-2 mb-4">
        <Zap size={12} style={{ color: 'var(--color-accent)' }} />
        Energy Monitoring
      </h3>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <StatCard
          icon={Zap}
          label="Total Energy"
          value={((energy.total_energy_j ?? 0) / 1000).toFixed(1)}
          unit="kJ"
        />
        <StatCard
          icon={Activity}
          label="Energy / Token"
          value={(energy.energy_per_token_j ?? 0).toFixed(3)}
          unit="J"
        />
        <StatCard
          icon={Thermometer}
          label="Avg Power"
          value={(energy.avg_power_w ?? 0).toFixed(1)}
          unit="W"
        />
        <StatCard
          icon={Hash}
          label="Total Requests"
          value={String(savings?.total_calls ?? telemetry?.total_requests ?? 0)}
        />
        <StatCard
          icon={Gauge}
          label="Thermal"
          value={thermalStatus.label}
        />
        <StatCard
          icon={Hash}
          label="Tokens Processed"
          value={formatNumber(savings?.total_tokens ?? telemetry?.total_tokens ?? 0)}
        />
      </div>

      {/* Chart */}
      {chartData.length > 1 && (
        <div className="h-48">
          <PowerLineChart data={chartData} />
        </div>
      )}
    </div>
  );
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}
