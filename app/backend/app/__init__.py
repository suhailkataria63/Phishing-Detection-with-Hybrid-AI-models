import os
import warnings

# Prevent noisy loky physical-core detection warnings on macOS environments.
if not os.environ.get("LOKY_MAX_CPU_COUNT"):
    logical = os.cpu_count() or 1
    os.environ["LOKY_MAX_CPU_COUNT"] = str(max(1, logical - 1))

warnings.filterwarnings(
    "ignore",
    message="Could not find the number of physical cores.*",
    category=UserWarning,
)
