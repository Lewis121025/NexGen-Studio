/**
 * Config Panel - 右侧上下文配置面板
 * 根据当前模式动态渲染配置选项
 */

'use client';

import { Settings2, Info } from 'lucide-react';

import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useStudioStore } from '@/lib/stores/studio';

export default function ConfigPanel() {
  const mode = useStudioStore((state) => state.mode);

  return (
    <TooltipProvider>
      <div className="h-full flex flex-col bg-surface-2">
        {/* 标题栏 */}
        <div className="p-4 border-b border-border/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings2 className="w-5 h-5 text-primary" />
              <h2 className="text-sm font-semibold text-foreground">
                {mode === 'general' ? '对话配置' : '创作设置'}
              </h2>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="w-6 h-6">
                  <Info className="w-4 h-4 text-muted-foreground" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-xs">
                <p className="text-xs">
                  这些参数配置会保存在本地。部分高级参数需要后端支持才能完全生效。
                </p>
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* 配置内容 */}
        <div className="flex-1 overflow-y-auto px-4 scrollbar-thin scrollbar-thumb-surface-3 scrollbar-track-transparent">
          {mode === 'general' ? <GeneralConfigPanel /> : <CreativeConfigPanel />}
        </div>
      </div>
    </TooltipProvider>
  );
}

// ==================== General 模式配置 ====================
function GeneralConfigPanel() {
  const generalConfig = useStudioStore((state) => state.generalConfig);
  const updateGeneralConfig = useStudioStore((state) => state.updateGeneralConfig);

  return (
    <div className="space-y-6 py-4">
      {/* 工具开关 */}
      <ConfigSection title="工具">
        <ConfigItem
          label="网络搜索"
          description="启用实时网络搜索 (Tavily)"
        >
          <Switch
            checked={generalConfig.enableSearch}
            onCheckedChange={(checked) =>
              updateGeneralConfig('enableSearch', checked)
            }
          />
        </ConfigItem>

        <Separator className="bg-border/30" />

        <ConfigItem
          label="代码执行"
          description="启用 Python 代码执行环境"
        >
          <Switch
            checked={generalConfig.enablePython}
            onCheckedChange={(checked) =>
              updateGeneralConfig('enablePython', checked)
            }
          />
        </ConfigItem>

        <Separator className="bg-border/30" />

        <ConfigItem label="对话记忆" description="启用上下文记忆">
          <Switch
            checked={generalConfig.enableMemory}
            onCheckedChange={(checked) =>
              updateGeneralConfig('enableMemory', checked)
            }
          />
        </ConfigItem>
      </ConfigSection>

      {/* 高级设置说明 */}
      <div className="text-xs text-muted-foreground text-center p-4 bg-surface-3/30 rounded-google">
        <p>更多高级参数（如 Temperature、Top-K）</p>
        <p className="mt-1">由后端配置统一管理</p>
      </div>
    </div>
  );
}

// ==================== Creative 模式配置 ====================
function CreativeConfigPanel() {
  const creativeConfig = useStudioStore((state) => state.creativeConfig);
  const updateCreativeConfig = useStudioStore((state) => state.updateCreativeConfig);

  return (
    <div className="space-y-6 py-4">
      {/* 风格设置 */}
      <ConfigSection title="创作风格">
        <ConfigItem label="视觉风格" description="选择分镜和视频风格">
          <Select
            value={creativeConfig.stylePreset}
            onValueChange={(value) =>
              updateCreativeConfig('stylePreset', value)
            }
          >
            <SelectTrigger className="w-full rounded-google bg-surface-3 border-border/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-google">
              <SelectItem value="cinematic">电影级</SelectItem>
              <SelectItem value="anime">动漫风格</SelectItem>
              <SelectItem value="realistic">写实</SelectItem>
              <SelectItem value="artistic">艺术抽象</SelectItem>
            </SelectContent>
          </Select>
        </ConfigItem>
      </ConfigSection>

      {/* 说明 */}
      <div className="text-xs text-muted-foreground text-center p-4 bg-surface-3/30 rounded-google space-y-2">
        <p className="font-medium">Creative 模式说明</p>
        <p>1. 输入视频需求描述</p>
        <p>2. AI 自动生成脚本</p>
        <p>3. 确认后生成分镜预览</p>
        <p>4. 渲染生成最终视频</p>
      </div>
    </div>
  );
}

// ==================== 辅助组件 ====================
function ConfigSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        {title}
      </h3>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function ConfigItem({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Label className="text-sm font-medium text-foreground">{label}</Label>
        </div>
      </div>
      {description && (
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
      )}
      {children}
    </div>
  );
}
