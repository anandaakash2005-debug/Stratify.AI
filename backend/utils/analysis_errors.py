"""Public-safe, typed pipeline failures. Never include provider bodies."""

class AnalysisError(RuntimeError):
    status = 502
    code = "AI_OUTPUT_INVALID"
    retryable = True

    def __init__(self, detail="The AI could not produce a complete report. Please retry."):
        super().__init__(detail)


class AITimeoutError(AnalysisError):
    status = 504
    code = "ANALYSIS_TIMEOUT"


class AIProviderError(AnalysisError):
    status = 503
    code = "AI_UNAVAILABLE"


class AIParameterError(AIProviderError):
    status = 502
    code = "AI_CONFIGURATION_ERROR"
    retryable = False


class AIRateLimitError(AIProviderError):
    status = 429
    code = "RATE_LIMITED"


class AITruncationError(AnalysisError):
    code = "AI_OUTPUT_TRUNCATED"

    def __init__(self, detail="The local AI reached its output-token limit before completing the report."):
        super().__init__(detail)


class AIReasoningExhaustedError(AITruncationError):
    code = "AI_REASONING_EXHAUSTED"


class AIEmptyResponseError(AnalysisError):
    code = "AI_OUTPUT_EMPTY"


class AIInvalidJSONError(AnalysisError):
    pass


class AISchemaError(AnalysisError):
    pass


class AnalysisConflict(AnalysisError):
    status = 409
    code = "REQUEST_CONFLICT"
    retryable = False


class AnalysisClaimConflictError(AnalysisConflict):
    code = "ANALYSIS_CLAIM_CONFLICT"


class AnalysisAlreadyProcessingError(AnalysisConflict):
    code = "ANALYSIS_IN_PROGRESS"
    retryable = True


class AnalysisLeaseExpiredError(AnalysisConflict):
    code = "ANALYSIS_LEASE_EXPIRED"
    retryable = True


class PersistenceError(AnalysisError):
    status = 503
    code = "PERSISTENCE_UNAVAILABLE"


class AnalysisPersistenceError(PersistenceError):
    code = "ANALYSIS_PERSISTENCE_FAILED"
    retryable = False
