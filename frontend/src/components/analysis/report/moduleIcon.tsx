/**
 * Иконка антифрод-модуля по его имени. Возвращает JSX, поэтому .tsx.
 */
import {
  Zap, Network, Layers, ArrowLeftRight, Store, Moon, Copy,
  CircleDollarSign, UserX, Activity,
} from 'lucide-react';

export function getModuleIcon(name: string) {
  const iconMap: Record<string, any> = {
    velocity: <Zap className="w-4 h-4" />,
    graph: <Network className="w-4 h-4" />,
    structuring: <Layers className="w-4 h-4" />,
    cross_reference: <ArrowLeftRight className="w-4 h-4" />,
    merchant_risk: <Store className="w-4 h-4" />,
    night_transactions: <Moon className="w-4 h-4" />,
    duplicate_payments: <Copy className="w-4 h-4" />,
    round_amounts: <CircleDollarSign className="w-4 h-4" />,
    profile_mismatch: <UserX className="w-4 h-4" />,
  };
  return iconMap[name] || <Activity className="w-4 h-4" />;
}
