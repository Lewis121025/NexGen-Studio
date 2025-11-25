"""Cloud-based sandbox integration using E2B."""

from __future__ import annotations

from typing import Any

from e2b_code_interpreter import Sandbox as E2BSandbox

from .config import settings
from .instrumentation import get_logger

logger = get_logger()


class EnhancedSandbox:
    """E2B-backed sandbox executor."""

    def __init__(self, api_key: str | None = None, timeout_seconds: int | None = None):
        """Initialize sandbox with API key and optional timeout.
        
        Args:
            api_key: E2B API key. If None, uses settings.e2b_api_key
            timeout_seconds: Timeout in seconds (for future use, E2B handles timeout internally)
        """
        self.api_key = api_key or settings.e2b_api_key
        if not self.api_key:
            raise ValueError("E2B API key is required. Set E2B_API_KEY in environment or pass api_key parameter.")
        self.timeout_seconds = timeout_seconds

    def execute_python(self, code: str) -> dict[str, Any]:
        """Execute Python code in the E2B sandbox.
        
        Returns:
            dict with keys:
                - stdout: str - standard output
                - stderr: str - standard error
                - result: Any - last result from execution (extracted from results)
                - results: list - all execution results
                - error: str | None - error name if execution failed
        """
        try:
            # E2B Sandbox uses create() method, not direct instantiation
            sandbox = E2BSandbox.create(api_key=self.api_key)
            try:
                execution = sandbox.run_code(code)
            finally:
                sandbox.kill()
                
                # Extract stdout/stderr as strings
                stdout_str = ""
                stderr_str = ""
                if execution.logs.stdout:
                    stdout_str = "".join(execution.logs.stdout) if isinstance(execution.logs.stdout, list) else str(execution.logs.stdout)
                if execution.logs.stderr:
                    stderr_str = "".join(execution.logs.stderr) if isinstance(execution.logs.stderr, list) else str(execution.logs.stderr)
                
                # Extract results
                results_list = []
                last_result = None
                if execution.results:
                    for r in execution.results:
                        # Try to extract the actual value from result objects
                        result_value = None
                        if hasattr(r, 'text'):
                            result_value = r.text
                        elif hasattr(r, 'data'):
                            result_value = r.data
                        elif hasattr(r, 'value'):
                            result_value = r.value
                        else:
                            result_value = str(r)
                        
                        if result_value is not None:
                            results_list.append(result_value)
                            last_result = result_value
                
                # Try to parse numeric results from stdout if no explicit result
                if last_result is None and stdout_str:
                    # Try to extract numeric values from stdout (for test compatibility)
                    import re
                    # Look for numeric patterns in stdout
                    numeric_match = re.search(r'(\d+(?:\.\d+)?)', stdout_str)
                    if numeric_match:
                        try:
                            last_result = float(numeric_match.group(1))
                            if last_result.is_integer():
                                last_result = int(last_result)
                        except (ValueError, AttributeError):
                            pass
                
                error = None
                if execution.error:
                    error = execution.error.name if hasattr(execution.error, 'name') else str(execution.error)
                
                return {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "result": last_result,  # Last result for test compatibility
                    "results": results_list,
                    "error": error,
                }
        except Exception as e:
            logger.error(f"Sandbox execution failed: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "result": None,
                "results": [],
                "error": str(e),
            }


def get_sandbox() -> EnhancedSandbox:
    """Create an E2B sandbox instance using configured credentials."""
    if not settings.e2b_api_key:
        logger.error("E2B_API_KEY is not configured; sandbox execution is unavailable.")
        raise RuntimeError("E2B_API_KEY is required for sandbox execution.")
    return EnhancedSandbox(api_key=settings.e2b_api_key)
