from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status_code"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)

JOBS_CLAIMED_TOTAL = Counter("jobs_claimed_total", "Total jobs claimed by workers", ["queue_id"])
JOBS_COMPLETED_TOTAL = Counter("jobs_completed_total", "Total jobs completed", ["queue_id"])
JOBS_FAILED_TOTAL = Counter("jobs_failed_total", "Total job failures", ["queue_id"])
JOBS_DEAD_LETTERED_TOTAL = Counter("jobs_dead_lettered_total", "Total jobs moved to DLQ", ["queue_id"])
JOB_EXECUTION_DURATION_SECONDS = Histogram(
    "job_execution_duration_seconds", "Job execution duration", ["queue_id"]
)
