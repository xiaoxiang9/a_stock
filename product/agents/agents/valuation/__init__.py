"""估值 Agent。

职责：
- 接收股票代码、公司名称和证据输入，输出结构化估值结果。
- 不直接依赖 data 层的配置加载器或数据取数实现。
"""

from .agent import ValuationAgent
from .data_agent import DataAcquisitionAgent
from .prefill import ValuationPrefillResult, prefill_valuation_request
from .providers import (
    AkShareEvidenceProvider,
    MxDataEvidenceProvider,
    MxSearchEvidenceProvider,
    TushareEvidenceProvider,
    WebSearchDeepseekEvidenceProvider,
)
from .schemas import (
    ValuationDataNeed,
    ValuationEvidenceAttempt,
    ValuationEvidenceBatch,
    ValuationEvidenceItem,
    ValuationRequest,
    ValuationResult,
)
from .workflow import ValuationResearchCoordinator, ValuationResearchOutcome

__all__ = [
    "ValuationAgent",
    "DataAcquisitionAgent",
    "ValuationDataNeed",
    "ValuationEvidenceAttempt",
    "ValuationEvidenceBatch",
    "ValuationEvidenceItem",
    "MxDataEvidenceProvider",
    "MxSearchEvidenceProvider",
    "ValuationRequest",
    "ValuationResult",
    "ValuationPrefillResult",
    "TushareEvidenceProvider",
    "ValuationResearchCoordinator",
    "ValuationResearchOutcome",
    "AkShareEvidenceProvider",
    "WebSearchDeepseekEvidenceProvider",
    "prefill_valuation_request",
]
