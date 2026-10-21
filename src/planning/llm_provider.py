"""
LLM Provider Abstraction: Deterministic mock provider, call budget tracking, prompt injection neutralization, and failure recovery.
"""
import time
from typing import Any, Dict, List, Optional
from src.config import CONFIG

class ModelCallBudgetExceeded(Exception):
    pass

class ToolCallBudgetExceeded(Exception):
    pass

class LLMProvider:
    def __init__(
        self,
        max_model_calls: int = CONFIG.MAX_MODEL_CALLS_PER_DECISION,
        max_tool_calls: int = CONFIG.MAX_TOOL_CALLS_PER_DECISION,
        timeout_s: float = CONFIG.LLM_TIMEOUT_SECONDS
    ):
        self.max_model_calls = max_model_calls
        self.max_tool_calls = max_tool_calls
        self.timeout_s = timeout_s
        self.model_calls_count = 0
        self.tool_calls_count = 0
        self.simulate_slow_down = False
        self.simulate_failure = False

    def reset_budgets(self):
        self.model_calls_count = 0
        self.tool_calls_count = 0

    def record_tool_call(self):
        self.tool_calls_count += 1
        if self.tool_calls_count > self.max_tool_calls:
            raise ToolCallBudgetExceeded(
                f"Tool calls exceeded budget: {self.tool_calls_count} > {self.max_tool_calls}"
            )

    def sanitize_untrusted_input(self, text: str) -> str:
        """
        Treats catalogue descriptions and user input as untrusted data.
        Removes / neutralizes potential prompt-injection patterns regardless of casing.
        """
        import re
        if not text:
            return ""
        adversarial_patterns = [
            r"system override",
            r"ignore previous instructions",
            r"send an urgent whatsapp",
            r"message every viewer",
            r"bypass policy"
        ]
        sanitized = text
        for pat in adversarial_patterns:
            sanitized = re.sub(pat, "[FILTERED_INJECTION]", sanitized, flags=re.IGNORECASE)
        return sanitized

    def generate_plan(
        self,
        viewer_id: str,
        goal_name: str,
        dialect: str,
        content_titles: List[str],
        untrusted_descriptions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        self.model_calls_count += 1
        if self.model_calls_count > self.max_model_calls:
            raise ModelCallBudgetExceeded(
                f"Model calls exceeded budget: {self.model_calls_count} > {self.max_model_calls}"
            )

        if self.simulate_failure:
            raise RuntimeError("Simulated LLM service 503 Unavailable")

        if self.simulate_slow_down:
            time.sleep(min(self.timeout_s + 0.1, 1.0))
            raise TimeoutError("LLM call timed out exceeding latency budget")

        # Sanitize any passed untrusted descriptions
        if untrusted_descriptions:
            for desc in untrusted_descriptions:
                self.sanitize_untrusted_input(desc)

        # Deterministic mock planning output
        confidence = 0.61
        confidence_reason = (
            f"Viewer matched with dialect {dialect} and eligible for goal {goal_name}. "
            f"Catalogue has {len(content_titles)} available titles matching genre preferences."
        )

        first_title = content_titles[0] if content_titles else "T0001"
        assumptions = [f"viewer has not started any episode of {first_title.replace('title:', '')}"]

        return {
            "recommended_action": "HOME_PAGE",
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "assumptions": assumptions
        }
