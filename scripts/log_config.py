# log_analyzer configuration

# Individual IPs to exclude from analysis
exclude_ips: list[str] = ["67.80.252.123"]

# CIDR ranges to exclude (e.g. "192.168.0.0/16")
exclude_ips_cidr: list[str] = []

# Exact-match user agents to exclude
exclude_user_agents_exact: list[str] = []

# Substring-match user agents to exclude
exclude_user_agents_substring: list[str] = [
    "headless",
    "python",
    "curl",
    "wget",
    "requests",
]

# HTTP status codes to exclude
exclude_status_codes: list[int] = []

# URI paths to exclude (exact match after stripping query string, e.g. "/favicon.ico")
exclude_paths: list[str] = [
    "/favicon.ico",
    "/robots.txt",
]
