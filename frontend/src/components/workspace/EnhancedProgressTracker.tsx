'use client';

import { motion } from 'framer-motion';
import { CheckCircle2, Clock, AlertCircle, Loader2 } from 'lucide-react';

import { cn } from '@/lib/utils';

interface Step {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'active' | 'completed' | 'error';
  progress?: number;
}

const steps: Step[] = [
  {
    id: 'brief',
    title: '概念构思',
    description: 'AI正在理解您的创意需求',
    status: 'pending'
  },
  {
    id: 'script',
    title: '脚本生成',
    description: '正在创作专业分镜脚本',
    status: 'pending'
  },
  {
    id: 'storyboard',
    title: '分镜制作',
    description: '生成精美的分镜图像',
    status: 'pending'
  },
  {
    id: 'render',
    title: '视频渲染',
    description: '合成最终视频内容',
    status: 'pending'
  }
];

export function EnhancedProgressTracker({ currentStep, progress }: { 
  currentStep: string; 
  progress?: number; 
}) {
  const currentIndex = steps.findIndex(step => step.id === currentStep);
  
  return (
    <div className="bg-surface-2 rounded-2xl p-6 border border-border/30">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold">创作进度</h3>
        {progress !== undefined && (
          <div className="text-sm text-muted-foreground">
            {Math.round(progress)}% 完成
          </div>
        )}
      </div>
      
      <div className="space-y-4">
        {steps.map((step, index) => {
          const isActive = index === currentIndex;
          const isCompleted = index < currentIndex;
          const Icon = isCompleted ? CheckCircle2 : 
                      step.status === 'error' ? AlertCircle :
                      isActive ? Loader2 : Clock;
                      
          return (
            <motion.div
              key={step.id}
              className={cn(
                "flex items-center gap-4 p-3 rounded-xl transition-all",
                isActive && "bg-primary/5 border border-primary/20",
                isCompleted && "bg-green-500/5"
              )}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <div className={cn(
                "flex items-center justify-center w-8 h-8 rounded-full",
                isActive && "bg-primary text-primary-foreground animate-pulse",
                isCompleted && "bg-green-500 text-white",
                !isActive && !isCompleted && "bg-surface-3 text-muted-foreground"
              )}>
                <Icon className={cn("w-4 h-4", isActive && "animate-spin")} />
              </div>
              
              <div className="flex-1">
                <h4 className="font-medium text-sm">{step.title}</h4>
                <p className="text-xs text-muted-foreground">{step.description}</p>
              </div>
              
              {isActive && progress !== undefined && (
                <div className="w-16 h-2 bg-surface-3 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-primary"
                    initial={{ width: '0%' }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

