"""通用任务处理 Agent 模块。

使用 ReAct 循环处理通用查询。ReAct (Reasoning + Acting) 是一种结合推理和行动的循环执行模式，
Agent 通过思考-行动-观察的循环逐步解决问题。
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..config import settings
from ..providers import LLMProvider, default_llm_provider


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
        from ..tooling import ToolRequest
        from ..general.models import GuardrailTriggered
        
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
            "Question: input question you must answer\n"
            "Thought: you should always think about what to do\n"
            "Action: action to take, should be one of the tool names\n"
            "Action Input: input to action as a valid JSON string matching the tool's parameter schema\n"
            "Observation: result of action\n"
            "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
            "Thought: I now know the final answer\n"
            "Final Answer: final answer to the original input question\n\n"
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
                    action_match = re.search(r"Action:\s*(.*?)\n", response)
                    input_match = re.search(r"Action Input:\s*(.*)", response, re.DOTALL)
                    
                    if not action_match or not input_match:
                        raise ValueError("Could not parse Action or Action Input")

                    action_name = action_match.group(1).strip()
                    action_input_str = input_match.group(1).strip()
                    
                    # 清理输入字符串：移除可能的 markdown 代码块和后续内容
                    if action_input_str.startswith("```"):
                        action_input_str = re.sub(r"^```(?:json)?\s*", "", action_input_str)
                        action_input_str = re.sub(r"\s*```.*$", "", action_input_str, flags=re.DOTALL)
                    
                    # 移除 "Observation:" 之后的内容（LLM 有时会继续生成）
                    if "\nObservation:" in action_input_str:
                        action_input_str = action_input_str.split("\nObservation:")[0]
                    if "Observation:" in action_input_str:
                        action_input_str = action_input_str.split("Observation:")[0]
                    
                    # 清理多余空白
                    action_input_str = action_input_str.strip()
                    
                    # 尝试解析 JSON
                    try:
                        action_input = json.loads(action_input_str)
                    except json.JSONDecodeError:
                        # 尝试提取 JSON 对象
                        json_match = re.search(r'\{[^{}]*\}', action_input_str)
                        if json_match:
                            try:
                                action_input = json.loads(json_match.group())
                            except json.JSONDecodeError:
                                # 回退到简单字符串输入（对于 web_search，使用 query 键）
                                action_input = {"query": action_input_str} if action_name == "web_search" else {"input": action_input_str}
                        else:
                            # 回退到简单字符串输入
                            action_input = {"query": action_input_str} if action_name == "web_search" else {"input": action_input_str}

                    # 执行工具（使用异步方法）
                    observation = f"Observation: Error: Tool '{action_name}' not found."
                    if action_name in tool_runtime._tools:
                        try:
                            result = await tool_runtime.execute_async(ToolRequest(name=action_name, input=action_input))
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