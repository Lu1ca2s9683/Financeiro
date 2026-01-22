import { Activity, AlertTriangle, CheckCircle } from 'lucide-react';

interface HealthCardProps {
  status: 'SAUDAVEL' | 'ATENCAO' | 'CRITICO';
  percentualPago: number;
}

export function HealthCard({ status, percentualPago }: HealthCardProps) {
  const config = {
    SAUDAVEL: {
      color: 'bg-emerald-50 text-emerald-700 border-emerald-100',
      icon: CheckCircle,
      label: 'Saudável',
      desc: 'Pagamentos em dia'
    },
    ATENCAO: {
      color: 'bg-yellow-50 text-yellow-700 border-yellow-100',
      icon: Activity,
      label: 'Atenção',
      desc: 'Monitore os prazos'
    },
    CRITICO: {
      color: 'bg-rose-50 text-rose-700 border-rose-100',
      icon: AlertTriangle,
      label: 'Crítico',
      desc: 'Atrasos relevantes'
    }
  };

  const current = config[status] || config.SAUDAVEL;
  const Icon = current.icon;

  return (
    <div className={`p-6 rounded-2xl border ${current.color} flex flex-col justify-between h-full`}>
      <div className="flex justify-between items-start">
        <div className="p-2 bg-white/50 rounded-lg">
          <Icon size={24} />
        </div>
        <span className="text-xs font-bold uppercase tracking-wider bg-white/50 px-2 py-1 rounded">
          {current.label}
        </span>
      </div>

      <div className="mt-4">
        <h3 className="text-3xl font-bold">{Math.round(percentualPago)}%</h3>
        <p className="text-sm font-medium opacity-90">das despesas pagas</p>
        <p className="text-xs mt-2 opacity-75">{current.desc}</p>
      </div>
    </div>
  );
}
