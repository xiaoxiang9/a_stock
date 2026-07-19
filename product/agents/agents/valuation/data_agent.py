"""估值 Agent 的数据获取协作层。

职责：
- 根据估值 Agent 提出的数据诉求检索补充证据。
- 根据诉求的优先级和可替代来源依次尝试不同 provider。
- 同一诉求可以同时保留多源证据，供上层模型统一交叉验证。
- 不做估值判断，只做证据获取和失败降级。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .providers import EvidenceProvider, build_default_providers
from .schemas import ValuationDataNeed, ValuationEvidenceAttempt, ValuationEvidenceBatch, ValuationRequest


def _normalize_source_name(source_name: str) -> str:
    """把外部来源名称归一为稳定标识。"""
    normalized = source_name.strip().lower()
    if "tushare" in normalized:
        return "tushare"
    if "akshare" in normalized or normalized in {"ak", "ak-share"}:
        return "akshare"
    if "mx-finance-data" in normalized:
        return "mx-data"
    if "mx-finance-search" in normalized:
        return "mx-search"
    if "mx-data" in normalized or "妙想" in normalized and "搜索" not in normalized and "search" not in normalized:
        return "mx-data"
    if "mx-search" in normalized or "妙想" in normalized and ("搜索" in normalized or "search" in normalized):
        return "mx-search"
    if "websearch" in normalized or "deepseek" in normalized:
        return "websearch-deepseek"
    return normalized


@dataclass(frozen=True)
class DataAcquisitionAgent:
    """估值数据获取 Agent。"""

    providers: list[EvidenceProvider] = field(default_factory=build_default_providers)

    def collect(
        self,
        request: ValuationRequest,
        needs: list[ValuationDataNeed],
        *,
        full_channel_expansion: bool = False,
    ) -> ValuationEvidenceBatch:
        """按数据诉求补充证据。

        这里不做“首个命中即停止”的收口，允许同一数据诉求由多个 provider
        同时返回证据，便于上层模型统一做交叉验证和口径消化。
        是否进入全渠道扫描由上层业务显式决定，数据 Agent 只负责按入参执行。
        """
        raw_items = []
        notes: list[str] = []
        failed_sources: list[str] = []
        attempts: list[ValuationEvidenceAttempt] = []
        for need in needs:
            matched = False
            source_order = self._build_source_order(need, full_channel_expansion=full_channel_expansion)
            for source_name in source_order:
                provider = self._pick_provider(source_name)
                if provider is None:
                    attempts.append(
                        ValuationEvidenceAttempt(
                            need_title=need.title,
                            provider_name=source_name,
                            status="unavailable",
                            evidence_count=0,
                            query=need.query,
                            message="provider not registered",
                        )
                    )
                    continue
                try:
                    new_items = provider.fetch(request, need)
                except Exception as exc:
                    attempts.append(
                        ValuationEvidenceAttempt(
                            need_title=need.title,
                            provider_name=provider.name,
                            status="failure",
                            evidence_count=0,
                            query=need.query,
                            message=str(exc),
                        )
                    )
                    notes.append(f"{source_name} 获取失败：{exc}")
                    continue
                if new_items:
                    raw_items.extend(new_items)
                    attempts.append(
                        ValuationEvidenceAttempt(
                            need_title=need.title,
                            provider_name=provider.name,
                            status="success",
                            evidence_count=len(new_items),
                            query=need.query,
                            message=f"补充 {len(new_items)} 条证据",
                        )
                    )
                    notes.append(f"{need.title} 已由 {source_name} 补充")
                    matched = True
                else:
                    attempts.append(
                        ValuationEvidenceAttempt(
                            need_title=need.title,
                            provider_name=provider.name,
                            status="empty",
                            evidence_count=0,
                            query=need.query,
                            message="provider returned no evidence",
                        )
                    )
            if not matched:
                failed_sources.append(need.title)
        notes.append("原始证据已保留，汇总与冲突裁决交由模型完成")
        return ValuationEvidenceBatch(items=raw_items, notes=notes, failed_sources=failed_sources, attempts=attempts)

    def _build_source_order(
        self,
        need: ValuationDataNeed,
        *,
        full_channel_expansion: bool = False,
    ) -> list[str]:
        """构造单条诉求的查询顺序。

        默认使用诉求里给出的优先级；当上层明确要求全渠道扫描时，再补齐所有未显式指定的
        provider，确保覆盖剩余来源。
        """
        source_order = list(need.preferred_sources or [
                "tushare",
                "akshare",
                "mx-finance-data",
                "mx-finance-search",
                "mx-data",
                "mx-search",
                "websearch-deepseek",
            ])
        normalized = {source.strip().lower() for source in source_order if source.strip()}
        if full_channel_expansion:
            for provider in self.providers:
                provider_name = provider.name.strip().lower()
                if provider_name not in normalized:
                    source_order.append(provider.name)
                    normalized.add(provider_name)
        return source_order

    def _pick_provider(self, source_name: str) -> EvidenceProvider | None:
        """按名称匹配 provider。"""
        normalized = _normalize_source_name(source_name)
        for provider in self.providers:
            if provider.name.lower() == normalized:
                return provider
        return None
