"use client";

import { 
  DollarSign, 
  AlertTriangle, 
  TrendingUp, 
  Activity,
  Eye
} from "lucide-react";
import { useEffect, useState } from "react";

import * as api from "@/lib/api";
import type { 
  GovernanceCostSummary, 
  GovernanceAuditEvent, 
  GovernanceUsageOverview 
} from "@/lib/api";

export default function GovernancePage() {
  const [costs, setCosts] = useState<GovernanceCostSummary[]>([]);
  const [auditEvents, setAuditEvents] = useState<GovernanceAuditEvent[]>([]);
  const [usage, setUsage] = useState<GovernanceUsageOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    void loadData();
  }, []);
  
  const loadData = async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    
    try {
      const [costsData, eventsData, usageData] = await Promise.all([
        api.getGovernanceCosts(),
        api.getGovernanceAuditEvents(20),
        api.getGovernanceUsageOverview(),
      ]);
      
      setCosts(costsData);
      setAuditEvents(eventsData);
      setUsage(usageData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setIsLoading(false);
    }
  };
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
          <p className="mt-4 text-gray-400">加载治理数据...</p>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-6">
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle className="h-5 w-5" />
          <p className="font-medium">加载失败</p>
        </div>
        <p className="mt-2 text-sm text-gray-400">{error}</p>
      </div>
    );
  }
  
  // 计算总成本
  const totalCost = costs.reduce((sum, item) => sum + item.current_cost, 0);
  const totalBudget = costs.reduce((sum, item) => sum + (item.budget_limit ?? 0), 0);
  const anomalyCount = costs.reduce((sum, item) => sum + item.anomaly_count, 0);
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">治理控制台</h1>
        <p className="mt-2 text-gray-400">
          监控系统成本、追踪审计日志、管理资源预算
        </p>
      </div>
      
      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="总支出"
          value={`$${totalCost.toFixed(2)}`}
          icon={<DollarSign className="h-5 w-5" />}
          trend={totalBudget > 0 ? `${((totalCost / totalBudget) * 100).toFixed(1)}% 已用` : undefined}
        />
        
        <MetricCard
          title="预算总额"
          value={`$${totalBudget.toFixed(2)}`}
          icon={<TrendingUp className="h-5 w-5" />}
          trend={`${costs.length} 个实体`}
        />
        
        <MetricCard
          title="异常数量"
          value={anomalyCount.toString()}
          icon={<AlertTriangle className="h-5 w-5" />}
          variant={anomalyCount > 0 ? "warning" : "default"}
        />
        
        <MetricCard
          title="事件总数"
          value={usage?.total_events.toString() ?? "0"}
          icon={<Activity className="h-5 w-5" />}
        />
      </div>
      
      {/* Cost Breakdown */}
      <div className="rounded-lg border border-white/10 bg-[#0F0F14]/80 backdrop-blur-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Eye className="h-5 w-5 text-blue-400" />
          <h2 className="text-xl font-semibold text-white">成本明细</h2>
        </div>
        
        {costs.length === 0 ? (
          <p className="text-gray-400 text-center py-8">暂无成本数据</p>
        ) : (
          <div className="space-y-2">
            {costs.map((item, idx) => (
              <CostItem key={idx} item={item} />
            ))}
          </div>
        )}
      </div>
      
      {/* Audit Log */}
      <div className="rounded-lg border border-white/10 bg-[#0F0F14]/80 backdrop-blur-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-purple-400" />
          <h2 className="text-xl font-semibold text-white">审计日志</h2>
        </div>
        
        {auditEvents.length === 0 ? (
          <p className="text-gray-400 text-center py-8">暂无审计事件</p>
        ) : (
          <div className="space-y-2">
            {auditEvents.map((event, idx) => (
              <AuditEventItem key={idx} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// 指标卡片组件
function MetricCard({ 
  title, 
  value, 
  icon, 
  trend, 
  variant = "default" 
}: { 
  title: string; 
  value: string; 
  icon: React.ReactNode; 
  trend?: string | undefined;
  variant?: "default" | "warning" | undefined;
}) {
  const bgColor = variant === "warning" 
    ? "bg-orange-500/10 border-orange-500/30" 
    : "bg-[#0F0F14]/80 border-white/10";
  const iconColor = variant === "warning" ? "text-orange-400" : "text-blue-400";
  
  return (
    <div className={`rounded-lg border backdrop-blur-xl p-4 ${bgColor}`}>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{title}</p>
        <div className={iconColor}>{icon}</div>
      </div>
      <p className="mt-2 text-2xl font-bold text-white">{value}</p>
      {trend && (
        <p className="mt-1 text-xs text-gray-500">{trend}</p>
      )}
    </div>
  );
}

// 成本明细条目
function CostItem({ item }: { item: GovernanceCostSummary }) {
  const percentage = item.budget_limit 
    ? (item.current_cost / item.budget_limit) * 100 
    : 0;
  
  const statusColor = item.is_paused 
    ? "text-orange-400" 
    : item.anomaly_count > 0 
    ? "text-red-400" 
    : "text-green-400";
  
  return (
    <div className="flex items-center justify-between rounded-lg bg-white/5 p-3 hover:bg-white/10 transition-colors">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <p className="font-medium text-white">{item.entity_id}</p>
          <span className="text-xs text-gray-500 px-2 py-0.5 rounded bg-white/5">
            {item.entity_type}
          </span>
          {item.is_paused && (
            <span className="text-xs text-orange-400 px-2 py-0.5 rounded bg-orange-500/10">
              已暂停
            </span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-4 text-sm text-gray-400">
          <span>成本: ${item.current_cost.toFixed(2)}</span>
          {item.budget_limit && (
            <span>预算: ${item.budget_limit.toFixed(2)}</span>
          )}
          {item.anomaly_count > 0 && (
            <span className="text-red-400">异常: {item.anomaly_count}</span>
          )}
        </div>
      </div>
      
      {item.budget_limit && (
        <div className="flex items-center gap-2">
          <div className="w-32 h-2 bg-white/10 rounded-full overflow-hidden">
            <div 
              className={`h-full ${statusColor} transition-all`}
              style={{ width: `${Math.min(percentage, 100)}%` }}
            />
          </div>
          <span className={`text-sm font-medium ${statusColor}`}>
            {percentage.toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
}

// 审计事件条目
function AuditEventItem({ event }: { event: GovernanceAuditEvent }) {
  const time = new Date(event.timestamp).toLocaleString('zh-CN');
  
  return (
    <div className="flex items-start gap-3 rounded-lg bg-white/5 p-3 hover:bg-white/10 transition-colors">
      <div className="flex-shrink-0 mt-0.5">
        <div className="h-2 w-2 rounded-full bg-blue-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium text-white">{event.name}</p>
          <span className="text-xs text-gray-500">{time}</span>
        </div>
        {Object.keys(event.attributes).length > 0 && (
          <div className="mt-1 text-xs text-gray-400 font-mono">
            {JSON.stringify(event.attributes, null, 2)}
          </div>
        )}
      </div>
    </div>
  );
}
