/**
 * Config Panel - 右侧上下文配置面板
 * 根据当前模式动态渲染配置选项
 */

'use client';

import { useStudioStore } from '@/lib/stores/studio';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Settings2, Info } from 'lucide-react';
// import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export default function ConfigPanel() {
  const mode = useStudioStore((state) => state.mode);

  return (
    <div className="h-full flex flex-col bg-surface-2">
      {/* 标题栏 */}
      <div className="p-4 border-b border-border/30">
        <div className="flex items-center gap-2">
          <Settings2 className="w-5 h-5 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">
            {mode === 'general' ? '对话配置' : '创作设置'}
          </h2>
        </div>
      </div>

      {/* 配置内容 */}
      <div className="flex-1 overflow-y-auto px-4 scrollbar-thin scrollbar-thumb-surface-3 scrollbar-track-transparent">
        {mode === 'general' ? <GeneralConfigPanel /> : <CreativeConfigPanel />}
      </div>
    </div>
  );
}

// ==================== General 模式配置 ====================
function GeneralConfigPanel() {
  const generalConfig = useStudioStore((state) => state.generalConfig);
  const updateGeneralConfig = useStudioStore((state) => state.updateGeneralConfig);

  return (
    <div className="space-y-6 py-4">
      {/* 模型参数 */}
      <ConfigSection title="模型参数">
        {/* Temperature */}
        <ConfigItem
          label="Temperature"
          description="控制输出的随机性,越高越创造性"
        >
          <div className="space-y-3">
            <Slider
              value={[generalConfig.temperature]}
              onValueChange={([value]) =>
                updateGeneralConfig({ temperature: value })
              }
              min={0}
              max={1}
              step={0.1}
              className="w-full"
            />
            <div className="text-xs text-right text-muted-foreground">
              {generalConfig.temperature.toFixed(1)}
            </div>
          </div>
        </ConfigItem>

        <Separator className="bg-border/30" />

        {/* Top-K */}
        <ConfigItem label="Top-K" description="采样候选词数量">
          <div className="space-y-3">
            <Slider
              value={[generalConfig.topK]}
              onValueChange={([value]) => updateGeneralConfig({ topK: value })}
              min={1}
              max={100}
              step={1}
              className="w-full"
            />
            <div className="text-xs text-right text-muted-foreground">
              {generalConfig.topK}
            </div>
          </div>
        </ConfigItem>

        <Separator className="bg-border/30" />

        {/* Max Tokens */}
        <ConfigItem label="Max Tokens" description="最大输出长度">
          <div className="space-y-3">
            <Slider
              value={[generalConfig.maxTokens]}
              onValueChange={([value]) =>
                updateGeneralConfig({ maxTokens: value })
              }
              min={256}
              max={4096}
              step={256}
              className="w-full"
            />
            <div className="text-xs text-right text-muted-foreground">
              {generalConfig.maxTokens}
            </div>
          </div>
        </ConfigItem>
      </ConfigSection>

      {/* 工具开关 */}
      <ConfigSection title="工具">
        <ConfigItem
          label="Google Search"
          description="启用实时网络搜索"
        >
          <Switch
            checked={generalConfig.enableSearch}
            onCheckedChange={(checked) =>
              updateGeneralConfig({ enableSearch: checked })
            }
          />
        </ConfigItem>

        <Separator className="bg-border/30" />

        <ConfigItem
          label="Python Sandbox"
          description="启用代码执行环境"
        >
          <Switch
            checked={generalConfig.enablePython}
            onCheckedChange={(checked) =>
              updateGeneralConfig({ enablePython: checked })
            }
          />
        </ConfigItem>

        <Separator className="bg-border/30" />

        <ConfigItem label="Memory" description="启用对话记忆">
          <Switch
            checked={generalConfig.enableMemory}
            onCheckedChange={(checked) =>
              updateGeneralConfig({ enableMemory: checked })
            }
          />
        </ConfigItem>
      </ConfigSection>

      {/* 重置按钮 */}
      <Button
        variant="outline"
        className="w-full rounded-google"
        onClick={() => {
          updateGeneralConfig({
            temperature: 0.7,
            topK: 40,
            topP: 0.95,
            maxTokens: 2048,
          });
        }}
      >
        恢复默认设置
      </Button>
    </div>
  );
}

// ==================== Creative 模式配置 ====================
function CreativeConfigPanel() {
  const creativeConfig = useStudioStore((state) => state.creativeConfig);
  const updateCreativeConfig = useStudioStore((state) => state.updateCreativeConfig);

  return (
    <div className="space-y-6 py-4">
      {/* 视频参数 */}
      <ConfigSection title="视频参数">
        {/* Provider 选择 */}
        <ConfigItem label="AI Provider" description="选择视频生成引擎">
          <Select
            value={creativeConfig.videoProvider}
            onValueChange={(value: 'runway' | 'pika' | 'runware') =>
              updateCreativeConfig({ videoProvider: value })
            }
          >
            <SelectTrigger className="w-full rounded-google bg-surface-3 border-border/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-google">
              <SelectItem value="runway">Runway Gen-3</SelectItem>
              <SelectItem value="pika">Pika 1.5</SelectItem>
              <SelectItem value="runware">Runware</SelectItem>
            </SelectContent>
          </Select>
        </ConfigItem>

        <Separator className="bg-border/30" />

        {/* 视频时长 */}
        <ConfigItem label="Duration" description="视频时长">
          <Select
            value={creativeConfig.videoDuration.toString()}
            onValueChange={(value) =>
              updateCreativeConfig({ videoDuration: parseInt(value) as 3 | 5 | 10 })
            }
          >
            <SelectTrigger className="w-full rounded-google bg-surface-3 border-border/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-google">
              <SelectItem value="3">3 秒</SelectItem>
              <SelectItem value="5">5 秒 (推荐)</SelectItem>
              <SelectItem value="10">10 秒</SelectItem>
            </SelectContent>
          </Select>
        </ConfigItem>

        <Separator className="bg-border/30" />

        {/* 宽高比 */}
        <ConfigItem label="Aspect Ratio" description="视频宽高比">
          <div className="grid grid-cols-3 gap-2">
            {(['16:9', '9:16', '1:1'] as const).map((ratio) => (
              <Button
                key={ratio}
                variant={
                  creativeConfig.videoRatio === ratio ? 'default' : 'outline'
                }
                size="sm"
                onClick={() => updateCreativeConfig({ videoRatio: ratio })}
                className="rounded-google"
              >
                {ratio}
              </Button>
            ))}
          </div>
        </ConfigItem>

        <Separator className="bg-border/30" />

        {/* 质量 */}
        <ConfigItem label="Quality" description="视频质量">
          <Select
            value={creativeConfig.videoQuality}
            onValueChange={(value: 'draft' | 'standard' | 'high') =>
              updateCreativeConfig({ videoQuality: value })
            }
          >
            <SelectTrigger className="w-full rounded-google bg-surface-3 border-border/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-google">
              <SelectItem value="draft">草稿 (快速)</SelectItem>
              <SelectItem value="standard">标准 (推荐)</SelectItem>
              <SelectItem value="high">高清 (慢)</SelectItem>
            </SelectContent>
          </Select>
        </ConfigItem>
      </ConfigSection>

      {/* 风格设置 */}
      <ConfigSection title="风格预设">
        <ConfigItem label="Style" description="选择视觉风格">
          <Select
            value={creativeConfig.stylePreset}
            onValueChange={(value) =>
              updateCreativeConfig({ stylePreset: value })
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

        <Separator className="bg-border/30" />

        {/* 分镜帧数 */}
        <ConfigItem label="Frames per Scene" description="每个场景的分镜数">
          <div className="space-y-3">
            <Slider
              value={[creativeConfig.framesPerScene]}
              onValueChange={([value]) =>
                updateCreativeConfig({ framesPerScene: value })
              }
              min={1}
              max={8}
              step={1}
              className="w-full"
            />
            <div className="text-xs text-right text-muted-foreground">
              {creativeConfig.framesPerScene} 帧
            </div>
          </div>
        </ConfigItem>
      </ConfigSection>
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
