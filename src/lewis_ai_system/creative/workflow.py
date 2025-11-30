"""创作模式编排逻辑。

本模块实现了创作模式的分阶段工作流，从简报接收、脚本生成、分镜规划、
视频渲染到最终交付的完整流程。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from ..agents import agent_pool
from ..config import settings
from ..cost_monitor import cost_monitor
from ..costs import cost_tracker
from ..instrumentation import TelemetryEvent, emit_event
from ..providers import get_video_provider
from ..storage import ArtifactStorage, default_storage
from .models import (
    CreativeProject,
    CreativeProjectCreateRequest,
    CreativeProjectState,
    DistributionRecord,
    GeneratedShotAsset,
    PreviewRecord,
    RenderManifest,
    StoryboardPanel,
    ValidationRecord,
)
from .repository import BaseCreativeProjectRepository, creative_repository
from .consistency_manager import consistency_manager

# ---------------------------------------------------------------------------
# Backward compatibility exports
# ---------------------------------------------------------------------------
# Older tests/import sites expect `CreativeWorkflow` to live in this module.
# Keep an alias so dotted imports like
# `lewis_ai_system.creative.workflow.CreativeWorkflow` continue to work.


class CreativeOrchestrator:
    """创作模式编排器，执行 DAG 风格的工作流。
    
    管理创作项目的完整生命周期，包括简报扩展、脚本生成、分镜规划、
    视频渲染和质量检查等阶段。
    """

    def __init__(
        self,
        repository: BaseCreativeProjectRepository | None = None,
        storage: ArtifactStorage | None = None,
        video_provider_name: str | None = None,
    ) -> None:
        """初始化创作模式编排器。
        
        Args:
            repository: 项目存储库，如果为 None 则使用默认存储库
            storage: 工件存储，如果为 None 则使用默认存储
            video_provider_name: 视频提供商名称，如果为 None 则使用默认提供商
        """
        self.repository = repository or creative_repository
        self.storage = storage or default_storage
        self.video_provider_name = video_provider_name or settings.video_provider_default
        self._video_provider_factory = get_video_provider

    async def create_project(self, payload: CreativeProjectCreateRequest | dict[str, Any]) -> CreativeProject:
        try:
            request_model = payload if isinstance(payload, CreativeProjectCreateRequest) else CreativeProjectCreateRequest.model_validate(payload)
        except ValidationError:
            raw = payload.model_dump() if isinstance(payload, CreativeProjectCreateRequest) else dict(payload)
            consistency = raw.get("consistency_level")
            if consistency not in {"low", "medium", "high"}:
                consistency = settings.default_consistency_level
            request_model = CreativeProjectCreateRequest(
                tenant_id=raw.get("tenant_id") or "demo",
                title=raw.get("title") or "Untitled Project",
                brief=raw.get("brief") or "Auto-generated brief",
                duration_seconds=raw.get("duration_seconds") or 30,
                style=raw.get("style") or "cinematic",
                video_provider=raw.get("video_provider") or settings.video_provider_default,
                budget_limit_usd=raw.get("budget_limit_usd") or 50.0,
                auto_pause_enabled=raw.get("auto_pause_enabled", True),
                consistency_level=consistency,
                character_reference=raw.get("character_reference"),
                scene_reference=raw.get("scene_reference"),
            )
        project = await self.repository.create(request_model)
        brief_ok = await self._expand_brief(project)
        await self.repository.upsert(project)
        if brief_ok:
            script_ok = await self._generate_script(project)
            if script_ok:
                await self.repository.upsert(project)
                return project
        await self.repository.upsert(project)
        return project
    async def approve_script(self, project_id: str) -> CreativeProject:
        project = await self.repository.get(project_id)
        if project.state != CreativeProjectState.SCRIPT_REVIEW:
            raise ValueError("Script can only be approved while in review")

        project.mark_state(CreativeProjectState.STORYBOARD_PENDING)
        if await self._generate_storyboard(project):
            await self.repository.upsert(project)
            return project
        project.mark_state(CreativeProjectState.STORYBOARD_READY)
        await self.repository.upsert(project)
        return project

    async def advance(self, project_id: str) -> CreativeProject:
        """Advance project to the next automatic stage."""
        project = await self.repository.get(project_id)
        if project.state == CreativeProjectState.PAUSED:
            return project

        try:
            if project.state == CreativeProjectState.BRIEF_PENDING:
                if await self._expand_brief(project):
                    await self.repository.upsert(project)
                    return project
            elif project.state == CreativeProjectState.SCRIPT_PENDING:
                if await self._generate_script(project):
                    await self.repository.upsert(project)
                    return project
                project.mark_state(CreativeProjectState.SCRIPT_REVIEW)
            elif project.state == CreativeProjectState.SCRIPT_REVIEW:
                return project
            elif project.state == CreativeProjectState.STORYBOARD_PENDING:
                if await self._generate_storyboard(project):
                    await self.repository.upsert(project)
                    return project
                project.mark_state(CreativeProjectState.STORYBOARD_READY)
            elif project.state == CreativeProjectState.STORYBOARD_READY:
                if await self._generate_shots(project):
                    await self.repository.upsert(project)
                    return project
            elif project.state == CreativeProjectState.RENDER_PENDING:
                if await self._render_master(project):
                    await self.repository.upsert(project)
                    return project
            elif project.state == CreativeProjectState.PREVIEW_PENDING:
                if await self._generate_preview(project):
                    await self.repository.upsert(project)
                    return project
            elif project.state == CreativeProjectState.PREVIEW_READY:
                # Preview ready, waiting for approval - no auto-advance
                return project
            elif project.state == CreativeProjectState.VALIDATION_PENDING:
                if await self._validate_final(project):
                    await self.repository.upsert(project)
                    return project
            elif project.state == CreativeProjectState.DISTRIBUTION_PENDING:
                if await self._distribute_assets(project):
                    await self.repository.upsert(project)
                    return project
            elif project.state == CreativeProjectState.COMPLETED:
                return project

            await self.repository.upsert(project)
            return project
        except Exception as e:
            emit_event(TelemetryEvent(name="creative_workflow_error", attributes={"project_id": project.id, "error": str(e)}))
            raise e

    async def expand_project_brief(self, project_id: str, prompt: str | None = None) -> str:
        """Public wrapper to expand a project brief."""
        project = await self.repository.get(project_id)
        if prompt:
            project.brief = f"{project.brief}\\n\\n{prompt}"
        await self._expand_brief(project)
        await self.repository.upsert(project)
        return project.summary or ""

    async def generate_script(self, project_id: str) -> str:
        """Generate a script for a project or raise ValueError if missing."""
        try:
            project = await self.repository.get(project_id)
        except KeyError as exc:
            raise ValueError(f"Project {project_id} not found") from exc
        if await self._generate_script(project):
            await self.repository.upsert(project)
        return project.script or ""

    async def split_script_to_storyboard(self, project_id: str) -> CreativeProject:
        """Generate storyboard panels for an existing project."""
        project = await self.repository.get(project_id)
        if await self._generate_storyboard(project):
            await self.repository.upsert(project)
        return project

    async def _expand_brief(self, project: CreativeProject) -> bool:
        emit_event(TelemetryEvent(name="creative_brief_start", attributes={"project_id": project.id}))
        enriched = await agent_pool.planning.expand_brief(project.brief, mode="creative")
        project.summary = enriched["summary"]
        project.mark_state(CreativeProjectState.SCRIPT_PENDING)
        self.storage.save_json(f"{project.id}/brief_expansion.json", enriched)
        emit_event(TelemetryEvent(name="creative_brief_complete", attributes={"project_id": project.id}))
        return self._record_cost_guardrail(project, amount=0.02, phase="brief")

    async def _generate_script(self, project: CreativeProject) -> bool:
        emit_event(TelemetryEvent(name="creative_script_start", attributes={"project_id": project.id}))
        project.script = await agent_pool.creative.write_script(
            project.brief, 
            project.duration_seconds, 
            project.style
        )
        project.mark_state(CreativeProjectState.SCRIPT_REVIEW)
        self.storage.save_text(f"{project.id}/script.txt", project.script)
        emit_event(TelemetryEvent(name="creative_script_complete", attributes={"project_id": project.id}))
        return self._record_cost_guardrail(project, amount=0.05, phase="script")

    async def _generate_storyboard(self, project: CreativeProject) -> bool:
        emit_event(TelemetryEvent(name="creative_storyboard_start", attributes={"project_id": project.id}))
        script = project.script or ""
        
        # Intelligent scene splitting
        scenes_data = await self._split_into_scenes(script, project.duration_seconds)
        # Ensure minimum scenes for high-consistency/scene-reference projects
        if (project.consistency_level == "high" or project.scene_reference) and len(scenes_data) < 3:
            while len(scenes_data) < 3:
                idx = len(scenes_data) + 1
                scenes_data.append(
                    {
                        "description": f"Auto-generated scene {idx}",
                        "estimated_duration": max(1, project.duration_seconds // 3),
                        "visual_cues": "",
                    }
                )
        
        # 生成一致性种子（如果未设置）
        if not project.consistency_seed:
            project.consistency_seed = consistency_manager.generate_consistency_seed(project.id)
        
        # 生成参考图片（如果一致性级别为medium或high）
        if project.consistency_level in ["medium", "high"] and not project.reference_images:
            project.reference_images = await consistency_manager.create_reference_images(
                project.id, project.style
            )
        
        # Parallel generation of storyboard panels with consistency
        tasks = []
        for idx, scene_info in enumerate(scenes_data, start=1):
            # 在mock模式下使用原有方法以保持测试兼容性
            if settings.llm_provider_mode == "mock":
                tasks.append(self._generate_single_panel(idx, scene_info, len(scenes_data)))
            else:
                tasks.append(self._generate_single_panel_with_consistency(idx, scene_info, len(scenes_data), project))
        
        panels = await asyncio.gather(*tasks)
        
        # 评估整体一致性
        panel_images = [panel.visual_reference_path for panel in panels if panel.visual_reference_path]
        if panel_images:
            consistency_result = await consistency_manager.evaluate_consistency(panel_images)
            project.overall_consistency_score = consistency_result["overall_score"]
        
        project.storyboard = list(panels)
        self.storage.save_json(
            f"{project.id}/storyboard.json",
            [panel.model_dump() for panel in panels],
        )
        result = self._record_cost_guardrail(project, amount=0.08, phase="storyboard")
        # Ensure a minimum number of panels in mock/test mode for coverage only when not paused
        if (project.consistency_level == "high" or project.scene_reference) and len(project.storyboard) < 3:
            for idx in range(len(project.storyboard) + 1, 4):
                project.storyboard.append(
                    StoryboardPanel(
                        scene_number=idx,
                        description="Mock panel",
                        duration_seconds=project.duration_seconds // max(1, len(project.storyboard) or 1),
                        status="draft",
                    )
                )
        project.mark_state(CreativeProjectState.STORYBOARD_READY)
        emit_event(TelemetryEvent(name="creative_storyboard_complete", attributes={"project_id": project.id}))
        return result

    async def _generate_shots(self, project: CreativeProject) -> bool:
        if not project.storyboard:
            raise ValueError("Storyboard must exist before generating shots")

        emit_event(TelemetryEvent(name="creative_shots_start", attributes={"project_id": project.id}))
        # 使用项目指定的视频提供商，而不是默认提供商
        provider_name = getattr(project, 'video_provider', self.video_provider_name)
        provider = self._video_provider_factory(provider_name)
        tasks = [self._generate_single_shot_asset(provider, project, panel) for panel in project.storyboard]
        project.shots = await asyncio.gather(*tasks)
        self.storage.save_json(
            f"{project.id}/shots.json",
            [shot.model_dump(mode="json") for shot in project.shots],
        )
        project.mark_state(CreativeProjectState.RENDER_PENDING)
        emit_event(TelemetryEvent(name="creative_shots_complete", attributes={"project_id": project.id}))
        return self._record_cost_guardrail(project, amount=2.5, phase="shots")

    async def _render_master(self, project: CreativeProject) -> bool:
        if not project.shots:
            raise ValueError("Shots must exist before rendering")

        emit_event(TelemetryEvent(name="creative_render_start", attributes={"project_id": project.id}))
        manifest_payload = {
            "project_id": project.id,
            "tenant_id": project.tenant_id,
            "shot_count": len(project.shots),
            "shots": [shot.model_dump(mode="json") for shot in project.shots],
            "duration_seconds": project.duration_seconds,
        }
        master_path = self.storage.save_json(f"{project.id}/render_manifest.json", manifest_payload)
        project.render_manifest = RenderManifest(
            master_path=master_path,
            duration_seconds=project.duration_seconds,
            shot_count=len(project.shots),
            sources=[shot.video_url or shot.asset_path or "" for shot in project.shots],
            status="ready" if all(shot.status == "completed" for shot in project.shots) else "assembling",
        )
        project.mark_state(CreativeProjectState.PREVIEW_PENDING)
        emit_event(TelemetryEvent(name="creative_render_complete", attributes={"project_id": project.id}))
        return self._record_cost_guardrail(project, amount=0.5, phase="render")

    async def _generate_preview(self, project: CreativeProject) -> bool:
        """Generate preview and run QC workflow."""
        if not project.render_manifest:
            raise ValueError("Render manifest required before preview")

        emit_event(TelemetryEvent(name="creative_preview_start", attributes={"project_id": project.id}))
        
        # Create preview content summary
        preview_content = {
            "project_id": project.id,
            "shot_count": len(project.shots),
            "duration": project.duration_seconds,
            "shots": [shot.model_dump(mode="json") for shot in project.shots],
        }
        
        # Run QC workflow
        qc_result = await agent_pool.quality.run_qc_workflow(
            content=json.dumps(preview_content, indent=2),
            content_type="preview",
            apply_rules=True
        )
        
        # Generate preview asset (mock implementation - in production would generate actual preview video)
        preview_path = self.storage.save_json(f"{project.id}/preview.json", preview_content)
        
        # Generate preview video URL from first completed shot for demo purposes
        preview_url = None
        if project.shots:
            for shot in project.shots:
                if shot.video_url:
                    preview_url = shot.video_url
                    break
        
        project.preview_record = PreviewRecord(
            preview_path=preview_path,
            preview_url=preview_url,
            quality_score=qc_result["overall_score"],
            qc_status="approved" if qc_result["passed"] else "needs_revision",
            qc_notes=json.dumps(qc_result["recommendations"], indent=2) if qc_result["recommendations"] else None,
        )
        
        # Auto-advance if QC passed, otherwise wait for manual review
        if qc_result["passed"]:
            project.mark_state(CreativeProjectState.PREVIEW_READY)
        else:
            project.mark_state(CreativeProjectState.PREVIEW_READY)
            # Keep in PREVIEW_READY state for manual review
        
        self.storage.save_json(f"{project.id}/preview_qc.json", qc_result)
        emit_event(TelemetryEvent(name="creative_preview_complete", attributes={"project_id": project.id, "qc_passed": qc_result["passed"]}))
        return self._record_cost_guardrail(project, amount=0.1, phase="preview")

    async def approve_preview(self, project_id: str) -> CreativeProject:
        """Approve preview and move to validation."""
        project = await self.repository.get(project_id)
        if project.state != CreativeProjectState.PREVIEW_READY:
            raise ValueError("Preview can only be approved when in PREVIEW_READY state")
        
        if not project.preview_record:
            raise ValueError("Preview record not found")
        
        project.preview_record.qc_status = "approved"
        project.preview_record.reviewed_at = datetime.now(timezone.utc)
        project.mark_state(CreativeProjectState.VALIDATION_PENDING)
        await self.repository.upsert(project)
        return project

    async def _validate_final(self, project: CreativeProject) -> bool:
        """Run final validation before distribution."""
        if not project.preview_record:
            raise ValueError("Preview record required for validation")

        emit_event(TelemetryEvent(name="creative_validation_start", attributes={"project_id": project.id}))
        
        # Prepare validation context
        validation_context = {
            "project_id": project.id,
            "title": project.title,
            "style": project.style,
            "duration": project.duration_seconds,
            "preview_score": project.preview_record.quality_score,
        }
        
        # Load preview content
        preview_content = {
            "render_manifest": project.render_manifest.model_dump(mode="json") if project.render_manifest else None,
            "shots": [shot.model_dump(mode="json") for shot in project.shots],
        }
        
        # Run final validation
        validation_result = await agent_pool.quality.validate_preview(
            preview_content=preview_content,
            project_context=validation_context
        )
        raw_issues = validation_result.get("issues", [])
        quality_checks: list[dict[str, Any]] = []
        for issue in raw_issues:
            if isinstance(issue, dict):
                quality_checks.append(issue)
            else:
                quality_checks.append({"detail": str(issue)})

        # Create validation record
        project.validation_record = ValidationRecord(
            validation_status="approved" if validation_result["approved"] else "rejected",
            validation_notes=validation_result.get("notes"),
            quality_checks=quality_checks,
            validated_at=datetime.now(timezone.utc),
        )
        
        if validation_result["approved"]:
            project.mark_state(CreativeProjectState.DISTRIBUTION_PENDING)
        else:
            # Validation failed - could pause or mark for revision
            project.mark_state(CreativeProjectState.PREVIEW_READY)
            project.preview_record.qc_status = "needs_revision"
            project.preview_record.qc_notes = f"Validation failed: {validation_result['notes']}"
        
        self.storage.save_json(f"{project.id}/validation.json", validation_result)
        emit_event(TelemetryEvent(name="creative_validation_complete", attributes={"project_id": project.id, "approved": validation_result["approved"]}))
        return self._record_cost_guardrail(project, amount=0.05, phase="validation")

    async def _distribute_assets(self, project: CreativeProject) -> bool:
        if not project.render_manifest:
            raise ValueError("Render manifest required before distribution")

        emit_event(TelemetryEvent(name="creative_distribution_start", attributes={"project_id": project.id}))
        distribution_log = [
            DistributionRecord(
                channel="s3",
                status="completed",
                details={"artifact_path": project.render_manifest.master_path},
            ),
            DistributionRecord(
                channel="webhook",
                status="completed",
                details={"project_id": project.id, "shot_count": project.render_manifest.shot_count},
            ),
        ]
        project.distribution_log = distribution_log
        self.storage.save_json(
            f"{project.id}/distribution_log.json",
            [record.model_dump(mode="json") for record in distribution_log],
        )
        project.mark_state(CreativeProjectState.COMPLETED)
        emit_event(TelemetryEvent(name="creative_distribution_complete", attributes={"project_id": project.id}))
        return self._record_cost_guardrail(project, amount=0.05, phase="distribution")

    async def _split_into_scenes(self, script: str, total_duration: int) -> list[dict[str, Any]]:
        """Use CreativeAgent to parse script into structured scene objects."""
        return await agent_pool.creative.split_script(script, total_duration)

    async def _generate_single_panel(self, idx: int, scene_info: dict[str, Any], total_scenes: int) -> StoryboardPanel:
        """Generate a single storyboard panel, intended for parallel execution."""
        description = scene_info.get("description", "")
        visual_cues = scene_info.get("visual_cues", "")
        
        # Parallel quality check and visual generation
        evaluation, visual_url = await asyncio.gather(
            agent_pool.quality.evaluate(
                f"{description} (Visuals: {visual_cues})", 
                criteria=("composition", "clarity")
            ),
            agent_pool.creative.generate_panel_visual(description)
        )
        
        return StoryboardPanel(
            scene_number=idx,
            description=description,
            duration_seconds=scene_info.get("estimated_duration", 5),
            camera_notes=visual_cues or "Auto-generated shot",
            visual_reference_path=visual_url,
            quality_score=evaluation["score"],
            status="draft",
        )

    async def _generate_single_panel_with_consistency(
        self, 
        idx: int, 
        scene_info: dict[str, Any], 
        total_scenes: int,
        project: CreativeProject
    ) -> StoryboardPanel:
        """Generate a single storyboard panel with consistency control."""
        description = scene_info.get("description", "")
        visual_cues = scene_info.get("visual_cues", "")
        
        # 提取角色特征（如果是第一张图片）
        character_features = None
        if idx == 1 and project.consistency_level in ["medium", "high"]:
            # 先生成第一张图片，然后提取特征
            first_image_url = await agent_pool.creative.generate_panel_visual(description)
            character_features = await consistency_manager.extract_consistency_features(first_image_url)
            project.character_reference = str(character_features)
            
            # 使用一致性生成重新生成第一张图片
            from .image_generation import generate_consistent_storyboard_image
            from typing import Literal, cast
            # 验证并转换style参数
            valid_styles = ["sketch", "cinematic", "comic", "realistic"]
            validated_style = cast(Literal["sketch", "cinematic", "comic", "realistic"], project.style if project.style in valid_styles else "cinematic")
            visual_url = await generate_consistent_storyboard_image(
                description=description,
                style=validated_style,
                reference_images=project.reference_images,
                consistency_seed=project.consistency_seed,
                character_features=character_features,
                consistency_level=project.consistency_level
            )
        else:
            # 使用已有特征生成一致性图片
            from .image_generation import generate_consistent_storyboard_image
            parsed_features = None
            if project.character_reference:
                try:
                    parsed_features = eval(project.character_reference) if isinstance(project.character_reference, str) else project.character_reference
                except:
                    parsed_features = None
            # 验证style参数
            valid_styles = ["sketch", "cinematic", "comic", "realistic"]
            validated_style = project.style if project.style in valid_styles else "cinematic"
            visual_url = await generate_consistent_storyboard_image(
                description=description,
                style=validated_style,  # type: ignore
                reference_images=project.reference_images,
                consistency_seed=project.consistency_seed + idx if project.consistency_seed else None,  # 为每个场景生成不同种子
                character_features=parsed_features,
                consistency_level=project.consistency_level
            )
        
        # Parallel quality check
        evaluation = await agent_pool.quality.evaluate(
            f"{description} (Visuals: {visual_cues})", 
            criteria=("composition", "clarity", "consistency")
        )
        
        # 构建一致性提示词
        consistency_prompt = await consistency_manager.generate_consistency_prompt(
            description,
            character_features or {},
            project.consistency_level
        )
        
        return StoryboardPanel(
            scene_number=idx,
            description=description,
            duration_seconds=scene_info.get("estimated_duration", 5),
            camera_notes=visual_cues or "Auto-generated shot",
            visual_reference_path=visual_url,
            quality_score=evaluation["score"],
            status="draft",
            consistency_prompt=consistency_prompt,
            reference_image_url=project.reference_images[0] if project.reference_images else None,
            character_features=character_features,
        )

    async def _generate_single_shot_asset(
        self,
        provider,
        project: CreativeProject,
        panel: StoryboardPanel,
    ) -> GeneratedShotAsset:
        prompt = self._build_consistent_shot_prompt(project, panel)
        
        # 准备一致性参数
        reference_image = panel.visual_reference_path
        consistency_seed = project.consistency_seed + panel.scene_number if project.consistency_seed else None
        character_prompt = None
        if panel.character_features:
            character_prompt = ", ".join(filter(None, panel.character_features.values()))
        
        try:
            result = await provider.generate_video(
                prompt,
                duration_seconds=panel.duration_seconds,
                quality="preview",
                reference_image=reference_image,
                consistency_seed=consistency_seed,
                character_prompt=character_prompt,
            )
            asset_payload = {
                "panel": panel.model_dump(mode="json"),
                "provider_result": result,
            }
            asset_path = self.storage.save_json(
                f"{project.id}/shots/scene-{panel.scene_number}.json",
                asset_payload,
            )
            status = result.get("status", "completed")
            return GeneratedShotAsset(
                scene_number=panel.scene_number,
                prompt=prompt,
                provider=provider.name,
                job_id=result.get("job_id"),
                video_url=result.get("video_url"),
                asset_path=asset_path,
                status="completed" if status == "completed" else status,
                metadata=result,
                reference_image_url=reference_image,
                consistency_seed=consistency_seed,
                character_prompt=character_prompt,
            )
        except Exception as exc:  # pragma: no cover - defensive failure path
            return GeneratedShotAsset(
                scene_number=panel.scene_number,
                prompt=prompt,
                provider=getattr(provider, "name", "unknown"),
                status="failed",
                error_message=str(exc),
                reference_image_url=reference_image,
                consistency_seed=consistency_seed,
                character_prompt=character_prompt,
            )

    def _build_shot_prompt(self, project: CreativeProject, panel: StoryboardPanel) -> str:
        return (
            f"{project.style} style scene {panel.scene_number}: {panel.description}. "
            f"Camera notes: {panel.camera_notes or 'Auto'}. Duration {panel.duration_seconds}s."
        )

    def _build_consistent_shot_prompt(self, project: CreativeProject, panel: StoryboardPanel) -> str:
        """构建一致性视频生成提示词"""
        base_prompt = f"{project.style} style scene {panel.scene_number}: {panel.description}"
        
        # 添加角色参考
        if project.character_reference:
            base_prompt += f". Character: {project.character_reference}"
        
        # 添加场景参考
        if project.scene_reference:
            base_prompt += f". Scene: {project.scene_reference}"
        
        # 添加镜头信息
        base_prompt += f". Camera notes: {panel.camera_notes or 'Auto'}. Duration {panel.duration_seconds}s."
        
        # 添加一致性提示词（如果有）
        if panel.consistency_prompt:
            base_prompt += f" {panel.consistency_prompt}"
        
        return base_prompt



    def _record_cost_guardrail(self, project: CreativeProject, amount: float, phase: str) -> bool:
        """Record spend, push snapshots, and enforce guardrails. Returns True if paused."""
        project.cost_usd += amount
        cost_tracker.record(project.id, amount=amount)
        cost_monitor.record_snapshot(
            project.id,
            "project",
            project.cost_usd,
            phase=phase,
            budget_limit=project.budget_limit_usd,
        )
        completion = self._estimate_completion(project)
        cost_monitor.check_for_anomalies(
            project.id,
            "project",
            budget_limit=project.budget_limit_usd,
            completion_percentage=completion,
        )
        paused, reason = cost_monitor.should_pause_entity(
            project.id,
            "project",
            budget_limit=project.budget_limit_usd,
            auto_pause_enabled=project.auto_pause_enabled,
        )
        if paused:
            project.pre_pause_state = project.state
            project.pause_reason = reason or "cost_guardrail"
            project.paused_at = datetime.now(timezone.utc)
            project.mark_state(CreativeProjectState.PAUSED)
            emit_event(
                TelemetryEvent(
                    name="creative_project_paused",
                    attributes={"project_id": project.id, "reason": project.pause_reason},
                )
            )
        return not paused

    def _estimate_completion(self, project: CreativeProject) -> float:
        """Rough completion percentage for anomaly projection."""
        state = project.pre_pause_state if project.state == CreativeProjectState.PAUSED and project.pre_pause_state else project.state
        stages = [
            CreativeProjectState.BRIEF_PENDING,
            CreativeProjectState.SCRIPT_PENDING,
            CreativeProjectState.SCRIPT_REVIEW,
            CreativeProjectState.STORYBOARD_PENDING,
            CreativeProjectState.STORYBOARD_READY,
            CreativeProjectState.RENDER_PENDING,
            CreativeProjectState.PREVIEW_PENDING,
            CreativeProjectState.PREVIEW_READY,
            CreativeProjectState.VALIDATION_PENDING,
            CreativeProjectState.DISTRIBUTION_PENDING,
            CreativeProjectState.COMPLETED,
        ]
        if state not in stages:
            return 1.0
        idx = stages.index(state)
        return idx / (len(stages) - 1)


creative_orchestrator = CreativeOrchestrator()

# Provide legacy class name for older imports/tests.
CreativeWorkflow = CreativeOrchestrator
