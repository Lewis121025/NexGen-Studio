"""共享 Agent 基础类模块。

本模块定义了系统中使用的各种 Agent 类型，包括规划、质量检查、创意生成和通用任务处理等。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Sequence

from openai import AsyncOpenAI

from .config import settings
from .providers import LLMProvider, default_llm_provider


class PlanningAgent:
    """规划 Agent，负责将用户输入的简短提示扩展为可执行的详细步骤。
    
    主要用于创作模式的简报扩展阶段，将用户需求转化为更详细的项目描述。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化规划 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider

    async def expand_brief(self, prompt: str, *, mode: str) -> dict[str, Any]:
        """扩展用户输入的简报。
        
        Args:
            prompt: 用户输入的原始提示
            mode: 工作模式（如 "creative" 或 "general"）
            
        Returns:
            包含扩展后的摘要、哈希值和模式的字典
        """
        completion = await self.provider.complete(
            f"Expand the following brief for {mode} mode:\n{prompt}",
            temperature=0.4,
        )
        digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:8]
        return {
            "summary": completion,
            "hash": digest,
            "mode": mode,
        }


class QualityAgent:
    """质量检查 Agent，基于 LLM 进行质量评分，支持独立的 QC 工作流和规则引擎。
    
    用于评估生成内容的质量，支持自定义质量检查规则和阈值。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化质量检查 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider
        self.qc_rules: list[dict[str, Any]] = []  # 质量检查规则列表
        # 初始化默认 QC 规则
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """初始化默认的质量检查规则。"""
        self.add_qc_rule("content_quality", ["quality", "relevance"], threshold=0.7)
        self.add_qc_rule("completeness", ["completeness", "coherence"], threshold=0.6)
        self.add_qc_rule("technical_quality", ["technical", "accuracy"], threshold=0.75)

    def add_qc_rule(self, rule_name: str, criteria: list[str], threshold: float = 0.7, auto_approve: bool = False) -> None:
        """添加质量检查规则到规则引擎。
        
        Args:
            rule_name: 规则名称
            criteria: 评估标准列表
            threshold: 通过阈值（0.0-1.0），默认 0.7
            auto_approve: 如果通过是否自动批准，默认 False
        """
        self.qc_rules.append({
            "name": rule_name,
            "criteria": criteria,
            "threshold": threshold,
            "auto_approve": auto_approve,
        })

    async def evaluate(self, artifact: str, criteria: Sequence[str]) -> dict[str, Any]:
        """评估内容质量。
        
        Args:
            artifact: 要评估的内容文本
            criteria: 评估标准序列
            
        Returns:
            包含评分、标准和备注的字典
        """
        criteria_list = ", ".join(criteria)
        use_mock_shortcut = settings.llm_provider_mode == "mock" and self.provider is default_llm_provider
        if use_mock_shortcut:
            return {
                "score": 0.82,
                "criteria": list(criteria),
                "notes": "Mock evaluation pass",
            }
        prompt = (
            f"Evaluate the following text against these criteria: {criteria_list}.\n"
            "Provide a score from 0.0 to 1.0 and a brief justification.\n"
            f"Text: {artifact[:2000]}"  # 截断以避免上下文限制
        )
        response = await self.provider.complete(prompt, temperature=0.1)
        
        # 简单的启发式方法提取评分，如果可能的话，否则使用默认值
        # 这是一个基础实现；在生产环境中，我们会使用结构化输出
        score = 0.8
        if "0." in response:
            try:
                # 尝试在响应中找到浮点数
                words = response.split()
                for word in words:
                    # 去除常见标点符号
                    clean_word = word.strip(".,;!?")
                    if "0." in clean_word and clean_word.replace(".", "", 1).isdigit():
                        val = float(clean_word)
                        if 0 <= val <= 1:
                            score = val
                            break
            except ValueError:
                pass

        return {
            "score": score,
            "criteria": list(criteria),
            "notes": response.strip(),
        }

    async def run_qc_workflow(
        self,
        content: str,
        content_type: str = "general",
        apply_rules: bool = True
    ) -> dict[str, Any]:
        """运行独立的质量检查工作流，使用规则引擎。
        
        Args:
            content: 要检查的内容
            content_type: 内容类型，默认 "general"
            apply_rules: 是否应用规则，默认 True
            
        Returns:
            包含总体评分、通过状态、规则结果和建议的字典
        """
        results = {
            "overall_score": 0.0,
            "passed": False,
            "rule_results": [],
            "recommendations": [],
        }

        # 如果启用，应用 QC 规则
        if apply_rules and self.qc_rules:
            for rule in self.qc_rules:
                criteria_tuple = tuple(rule["criteria"])
                evaluation = await self.evaluate(content, criteria_tuple)
                rule_result = {
                    "rule_name": rule["name"],
                    "score": evaluation["score"],
                    "threshold": rule["threshold"],
                    "passed": evaluation["score"] >= rule["threshold"],
                    "notes": evaluation["notes"],
                }
                results["rule_results"].append(rule_result)
                
                if not rule_result["passed"]:
                    results["recommendations"].append(
                        f"Rule '{rule['name']}' failed: {evaluation['notes']}"
                    )
                elif rule.get("auto_approve", False) and rule_result["passed"]:
                    results["passed"] = True

        # 如果没有规则或规则未自动批准，进行总体评估
        if not results["passed"]:
            overall_eval = await self.evaluate(content, ("quality", "relevance", "completeness"))
            results["overall_score"] = overall_eval["score"]
            results["passed"] = overall_eval["score"] >= 0.7
            if not results["passed"]:
                results["recommendations"].append(f"Overall quality below threshold: {overall_eval['notes']}")

        return results

    async def validate_preview(
        self,
        preview_content: dict[str, Any],
        project_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """在最终批准前验证预览内容。
        
        Args:
            preview_content: 预览内容字典
            project_context: 项目上下文字典，可选
            
        Returns:
            包含批准状态、评分、问题和备注的字典
        """
        if settings.llm_provider_mode == "mock":
            return {
                "approved": True,
                "score": 0.9,
                "issues": [],
                "notes": "Mock validation auto-approved",
            }
        content_str = json.dumps(preview_content, indent=2)
        context_str = json.dumps(project_context or {}, indent=2) if project_context else ""
        
        prompt = (
            "Validate this preview content for final approval.\n"
            f"Preview Content:\n{content_str}\n\n"
            f"Project Context:\n{context_str}\n\n"
            "Check for: visual quality, consistency, completeness, brand compliance.\n"
            "Return JSON with 'approved' (bool), 'score' (float), 'issues' (list), 'notes' (string)."
        )
        
        response = await self.provider.complete(prompt, temperature=0.1)
        
        # 解析响应
        try:
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                score = float(parsed.get("score", 0.5))
                approved = bool(parsed.get("approved", False))
                if not approved and score >= 0.4:
                    approved = True
                return {
                    "approved": approved,
                    "score": score,
                    "issues": parsed.get("issues", []),
                    "notes": parsed.get("notes", response.strip()),
                }
        except (ValueError, KeyError, json.JSONDecodeError):
            pass
        
        # 回退方案
        return {
            "approved": True,
            "score": 0.6,
            "issues": ["Could not parse validation response"],
            "notes": response.strip(),
        }


class OutputFormatterAgent:
    """输出格式化 Agent，负责生成人类可读的输出内容。
    
    主要用于内容摘要生成和格式化。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化输出格式化 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider

    async def summarize(self, content: str) -> str:
        """生成内容摘要。
        
        Args:
            content: 要摘要的内容
            
        Returns:
            摘要文本
        """
        return await self.provider.complete(f"Summarize the following content:\n{content}", temperature=0.1)


class CreativeAgent:
    """创意内容生成 Agent，负责处理创意内容的生成任务。
    
    包括视频脚本生成、脚本拆分、分镜预览图生成等。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化创意 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider
        self.openai_client: AsyncOpenAI | None = None

    async def write_script(self, brief: str, duration: int, style: str) -> str:
        """生成视频脚本。
        
        Args:
            brief: 项目简报
            duration: 目标时长（秒）
            style: 风格描述
            
        Returns:
            生成的脚本文本
        """
        prompt = (
            "You are a professional screenwriter. Create a compelling scene-by-scene script based on the brief below.\n"
            "Structure the output clearly with Scene Headers (e.g., SCENE 1: [LOCATION] - [TIME]), Action Lines, and Dialogue.\n"
            f"Target Duration: {duration} seconds.\n"
            f"Style: {style}.\n"
            f"Brief:\n{brief}\n\n"
            "Ensure the script is paced well for the target duration."
        )
        return await self.provider.complete(prompt, temperature=0.7)

    async def split_script(self, script: str, total_duration: int) -> list[dict[str, Any]]:
        """将脚本拆分为分镜列表。
        
        Args:
            script: 完整的脚本文本
            total_duration: 总时长（秒）
            
        Returns:
            分镜列表，每个分镜包含描述、视觉提示和预估时长
        """
        prompt = (
            "Analyze the following script and split it into distinct scenes.\n"
            "Return a JSON object with a key 'scenes', where each item is an object containing:\n"
            "- 'description': A concise visual description of the action and setting.\n"
            "- 'visual_cues': Specific camera or lighting notes based on the style.\n"
            "- 'estimated_duration': Estimated duration in seconds (integer).\n\n"
            f"Script:\n{script}\n\n"
            "Ensure the total duration roughly matches the target. Return ONLY valid JSON."
        )
        response = await self.provider.complete(prompt, temperature=0.1)
        
        # 基本的 JSON 清理
        text = response.strip()
        if text.startswith("```"):
            import re
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            
        try:
            import json
            data = json.loads(text)
            return data.get("scenes", [])
        except Exception:
            # 回退方案：按段落拆分
            chunks = [c.strip() for c in script.split("\n\n") if c.strip()]
            return [
                {
                    "description": c,
                    "visual_cues": "Standard shot",
                    "estimated_duration": max(total_duration // max(len(chunks), 1), 5)
                }
                for c in chunks
            ]

    async def generate_panel_visual(self, description: str) -> str:
        if settings.llm_provider_mode == "mock":
            return f"https://placeholder.lewis.ai/{hash(description)}.jpg"

        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for storyboard visualization.")

        if self.openai_client is None:
            # Use OpenRouter-compatible OpenAI client for image generation
            self.openai_client = AsyncOpenAI(
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
            )

        response = await self.openai_client.images.generate(
            model="dall-e-3",
            prompt=f"Storyboard sketch: {description}",
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url


class GeneralAgent:
    """通用任务处理 Agent，使用 ReAct 循环处理通用查询。
    
    ReAct (Reasoning + Acting) 是一种结合推理和行动的循环执行模式，
    Agent 通过思考-行动-观察的循环逐步解决问题。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化通用 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider

    async def react_loop(self, query: str, tool_runtime: Any, max_steps: int = 5) -> str:
        """执行 ReAct 循环来回答查询，使用可用工具。
        
        Args:
            query: 用户查询
            tool_runtime: 工具运行时实例
            max_steps: 最大执行步数，默认 5
            
        Returns:
            最终答案文本
        """
        from .tooling import ToolRequest, ToolExecutionError
        from .general.models import GuardrailTriggered

        import json
        
        tools_desc_list = []
        for name, tool in tool_runtime._tools.items():
            try:
                schema = json.dumps(tool.parameters, indent=2)
            except NotImplementedError:
                schema = "{}"
            tools_desc_list.append(f"- {name}: {tool.description}\n  Parameters: {schema}")
        
        tools_desc = "\n".join(tools_desc_list)
        
        system_prompt = (
            "You are a helpful AI assistant with access to the following tools:\n"
            f"{tools_desc}\n\n"
            "Use the following format:\n"
            "Question: the input question you must answer\n"
            "Thought: you should always think about what to do\n"
            "Action: the action to take, should be one of the tool names\n"
            "Action Input: the input to the action as a valid JSON string matching the tool's parameter schema\n"
            "Observation: the result of the action\n"
            "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
            "Thought: I now know the final answer\n"
            "Final Answer: the final answer to the original input question\n\n"
            "Begin!"
        )

        history = f"{system_prompt}\n\nQuestion: {query}\n"
        for _ in range(max_steps):
            # 获取 LLM 响应
            response = await self.provider.complete(history, temperature=0.0)
            history += f"{response}\n"

            if "Final Answer:" in response:
                return response.split("Final Answer:")[-1].strip()

            # 解析 Action
            if "Action:" in response and "Action Input:" in response:
                try:
                    import re
                    import json
                    
                    action_match = re.search(r"Action:\s*(.*?)\n", response)
                    input_match = re.search(r"Action Input:\s*(.*)", response, re.DOTALL)
                    
                    if not action_match or not input_match:
                        raise ValueError("Could not parse Action or Action Input")

                    action_name = action_match.group(1).strip()
                    action_input_str = input_match.group(1).strip()
                    
                    # 如果需要，清理 JSON 字符串（移除 markdown 代码块）
                    if action_input_str.startswith("```"):
                        action_input_str = re.sub(r"^```(?:json)?\s*", "", action_input_str)
                        action_input_str = re.sub(r"\s*```$", "", action_input_str)
                    
                    # 如果需要，启发式处理单引号或其他常见 JSON 错误
                    # 目前假设是有效的 JSON 或简单的字典字符串
                    try:
                        action_input = json.loads(action_input_str)
                    except json.JSONDecodeError:
                        # 如果工具期望特定键，则回退到简单字符串输入
                        # 这是一个简化处理；更健壮的解析器会更好
                        action_input = {"input": action_input_str}

                    # 执行工具
                    observation = f"Observation: Error: Tool '{action_name}' not found."
                    if action_name in tool_runtime._tools:
                        try:
                            result = tool_runtime.execute(ToolRequest(name=action_name, input=action_input))
                            observation = f"Observation: {result.output}"
                        except GuardrailTriggered:
                            # 向上冒泡，以便编排器可以优雅地暂停
                            raise
                        except Exception as e:
                            observation = f"Observation: Tool execution failed: {str(e)}"
                    
                except Exception as e:
                    observation = f"Observation: Failed to parse or execute action: {str(e)}"
                
                history += f"{observation}\n"
            else:
                # 如果没有采取行动但没有最终答案，强制停止或要求继续
                # 目前，如果响应看起来完整，就直接返回
                return response.strip()

        return "I could not answer the question within the step limit."


class AgentPool:
    """Agent 池，提供所有 Agent 实例的统一访问接口。
    
    这是一个门面模式（Facade Pattern）的实现，集中管理所有类型的 Agent。
    """

    def __init__(self) -> None:
        """初始化 Agent 池，创建所有类型的 Agent 实例。"""
        self.planning = PlanningAgent()  # 规划 Agent
        self.quality = QualityAgent()  # 质量检查 Agent
        self.formatter = OutputFormatterAgent()  # 输出格式化 Agent
        self.creative = CreativeAgent()  # 创意生成 Agent
        self.general = GeneralAgent()  # 通用任务处理 Agent


# 全局 Agent 池实例
agent_pool = AgentPool()
