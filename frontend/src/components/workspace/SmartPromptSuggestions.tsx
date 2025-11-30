'use client';

import { Lightbulb, Zap, Target, Film } from 'lucide-react';
import { useState } from 'react';
import type { ElementType } from 'react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

interface Suggestion {
  id: string;
  title: string;
  description: string;
  icon: ElementType;
  prompt: string;
  category: string;
}

const suggestions: Suggestion[] = [
  {
    id: '1',
    title: '产品宣传片',
    description: '专业的产品展示视频',
    icon: Target,
    prompt: '创建30秒产品宣传片，展示[产品名称]的核心功能和优势，强调[关键卖点]，风格现代简洁，适合社交媒体传播',
    category: '商业'
  },
  {
    id: '2',
    title: '教程视频',
    description: '清晰的教学演示',
    icon: Zap,
    prompt: '制作5分钟教程视频，详细展示[技能/软件]的使用步骤，分步骤演示，包含实际操作界面，适合初学者',
    category: '教育'
  },
  {
    id: '3',
    title: '故事短片',
    description: '富有情感的叙事内容',
    icon: Film,
    prompt: '创作一个1分钟的情感故事短片，主题围绕[情感/故事线索]，包含角色对话和情节发展，风格温暖治愈',
    category: '创意'
  }
];

export function SmartPromptSuggestions({ onSelect }: { onSelect: (prompt: string) => void }) {
  const [selectedCategory, setSelectedCategory] = useState<string>('全部');
  
  const categories = ['全部', '商业', '教育', '创意'];
  const filteredSuggestions = selectedCategory === '全部' 
    ? suggestions 
    : suggestions.filter(s => s.category === selectedCategory);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Lightbulb className="w-5 h-5 text-yellow-500" />
        <h3 className="font-semibold text-sm">智能建议</h3>
      </div>
      
      <div className="flex gap-2 flex-wrap">
        {categories.map((category) => (
          <Button
            key={category}
            variant={selectedCategory === category ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedCategory(category)}
            className="text-xs"
          >
            {category}
          </Button>
        ))}
      </div>

      <div className="grid gap-2 sm:gap-3">
        {filteredSuggestions.map((suggestion) => {
          const Icon = suggestion.icon;
          return (
            <Card 
              key={suggestion.id}
              className="p-3 sm:p-4 cursor-pointer hover:bg-surface-2 transition-colors border-border/50 hover:border-primary/30 active:scale-95 touch-manipulation"
              onClick={() => onSelect(suggestion.prompt)}
            >
              <div className="flex items-start gap-3">
                <div className="p-1.5 sm:p-2 rounded-lg bg-primary/10 flex-shrink-0">
                  <Icon className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-xs sm:text-sm mb-1 leading-tight">{suggestion.title}</h4>
                  <p className="text-xs text-muted-foreground mb-2 line-clamp-2">{suggestion.description}</p>
                  <span className="inline-block px-1.5 sm:px-2 py-0.5 sm:py-1 bg-surface-3 text-xs rounded-full text-muted-foreground">
                    {suggestion.category}
                  </span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
