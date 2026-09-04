from vehicle_search_utils.settings import PROJECT_ROOT

EVALS_DIR = PROJECT_ROOT / "evals"
DATASETS_DIR = EVALS_DIR / "datasets"
REPORTS_DIR = PROJECT_ROOT / "data" / "evaluation"

DEFAULT_CASES_PATH = DATASETS_DIR / "agent_cases.json"
DEFAULT_VOICE_OUTPUT_PATH = REPORTS_DIR / "voice_latency_results.json"

DEFAULT_MIN_PASS_RATE = 90.0
DEFAULT_DELAY_SECONDS = 0.0
REPORT_RETENTION_COUNT = 5
