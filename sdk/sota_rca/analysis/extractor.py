"""Shared extraction layer for trajectory analysis.

Extracts structured information from agent trajectories:
- Service names from thought/action/result
- Data type classification (logs/metrics/traces)
- Query intent classification (7 categories)
- Ground truth context for path analysis
"""

import json
import re
from dataclasses import dataclass, field

from ..data.causal_graph import CausalGraph

# ── Constants ────────────────────────────────────────────────────────────────

SERVICE_PATTERN = re.compile(r"\bts-[a-z0-9][-a-z0-9]*\b")

# Matches "xxx service" or "xxx yyy service" (1-3 word stems before "service")
# Uses a non-greedy approach: only captures the 1-3 words immediately before "service"
NL_SERVICE_1W = re.compile(r"\b([a-z][a-z0-9]*)\s+service\b", re.IGNORECASE)
NL_SERVICE_2W = re.compile(r"\b([a-z][a-z0-9]*[-\s][a-z][a-z0-9]*)\s+service\b", re.IGNORECASE)
NL_SERVICE_3W = re.compile(r"\b([a-z][a-z0-9]*[-\s][a-z][a-z0-9]*[-\s][a-z][a-z0-9]*)\s+service\b", re.IGNORECASE)

# Matches "xxx-service" without ts- prefix (e.g., "preserve-service", "travel-plan-service")
# Uses a lookbehind to skip if preceded by "ts-" (with 1 extra char for word boundary)
NO_PREFIX_SERVICE_PATTERN = re.compile(r"(?<![a-z-])(?<!ts-)([a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*-service)\b")

# Known non-ts infrastructure service names that appear in causal graphs
NON_TS_SERVICES = {"loadgenerator", "mysql", "redis", "rabbitmq", "nacos", "mongodb", "kafka", "zookeeper"}

# Service-like names in results that should map to known services
# e.g., "loadgenerator-service" -> "loadgenerator", "kubernetes-endpoints" is infra noise (skip)
RESULT_SERVICE_ALIASES = {
    "loadgenerator-service": "loadgenerator",
}

# ── Known Service Vocabulary (TrainTicket system) ──────────────────────────────
# Complete whitelist of all known services. Used to validate fuzzy-extracted candidates.
# Organized by category for readability; flattened into lookup sets below.
_KNOWN_SERVICES: list[str] = [
    # Top-Level Services
    "ts-route-plan-service", "ts-travel-service", "ts-travel2-service",
    "ts-preserve-service", "ts-travel-plan-service", "ts-cancel-service",
    # Core Services
    "ts-basic-service", "ts-order-service", "ts-route-service",
    "ts-seat-service", "ts-order-other-service", "ts-train-service",
    "ts-station-service", "ts-inside-payment-service", "ts-payment-service",
    # Auxiliary Services
    "ts-food-service", "ts-security-service", "ts-user-service",
    "ts-config-service", "ts-consign-service", "ts-contacts-service",
    "ts-auth-service", "ts-price-service", "ts-assurance-service",
    "ts-train-food-service", "ts-station-food-service",
    "ts-verification-code-service", "ts-consign-price-service",
    # Frontend
    "ts-ui-dashboard",
    # Other known services (not in GT but exist in system)
    "ts-delivery-service", "ts-notification-service", "ts-food-map-service",
    "ts-news-service", "ts-rebook-service", "ts-ticket-office-service",
    "ts-voucher-service", "ts-admin-service", "ts-execute-service",
    # Admin sub-services
    "ts-admin-basic-info-service", "ts-admin-order-service",
    "ts-admin-route-service", "ts-admin-travel-service", "ts-admin-user-service",
    # Infrastructure / other
    "ts-avatar-service", "ts-gateway-service",
    # RCABench dataset-specific services (found via service_name field in parquet data)
    "ts-food-delivery-service", "ts-preserve-other-service", "ts-wait-order-service",
]

# Normalized form -> canonical name for fast lookup
_KNOWN_SVC_NORMALIZED: dict[str, str] = {}
# Bare stems (e.g., "preserve", "travelplan", "insidepayment") -> canonical name
_KNOWN_SVC_STEMS: dict[str, str] = {}

def _init_known_service_lookups() -> None:
    """Build lookup tables from _KNOWN_SERVICES (called once at import time)."""
    for svc in _KNOWN_SERVICES:
        norm = _normalize_service(svc)
        _KNOWN_SVC_NORMALIZED[norm] = svc
        # Bare stem: strip ts- prefix and -service suffix, remove hyphens
        bare = svc.lower()
        if bare.startswith("ts-"):
            bare = bare[3:]
        if bare.endswith("-service"):
            bare = bare[:-8]
        bare_joined = bare.replace("-", "")
        _KNOWN_SVC_STEMS[bare_joined] = svc
        # Also add hyphenated form as stem
        _KNOWN_SVC_STEMS[bare] = svc
        # Add compound form with "service" suffix (e.g., "foodservice", "orderservice")
        # This handles NL text like "foodservice endpoints" or "orderservice/order/refresh"
        _KNOWN_SVC_STEMS[bare_joined + "service"] = svc
    # Add infra services
    for svc in NON_TS_SERVICES:
        _KNOWN_SVC_NORMALIZED[svc] = svc
        _KNOWN_SVC_STEMS[svc] = svc
    # Add common aliases (agent misspellings / abbreviations)
    _KNOWN_SVC_STEMS["dashboard"] = "ts-ui-dashboard"
    # Agent sometimes writes ts-mysql-mysql instead of mysql
    _KNOWN_SVC_NORMALIZED["mysql_mysql"] = "mysql"
    # GT causal graph uses "loadgenerator-service" as alias for "loadgenerator"
    _KNOWN_SVC_NORMALIZED["loadgenerator_service"] = "loadgenerator"
    # Near-miss aliases: agent typos that should map to real services
    _KNOWN_SVC_NORMALIZED["contact_service"] = "ts-contacts-service"
    _KNOWN_SVC_NORMALIZED["inside_pay_service"] = "ts-inside-payment-service"
    _KNOWN_SVC_NORMALIZED["verifycode_service"] = "ts-verification-code-service"
    _KNOWN_SVC_NORMALIZED["pay_service"] = "ts-payment-service"
    _KNOWN_SVC_NORMALIZED["verification_service"] = "ts-verification-code-service"
    _KNOWN_SVC_STEMS["verifycode"] = "ts-verification-code-service"
    _KNOWN_SVC_STEMS["insidepay"] = "ts-inside-payment-service"
    _KNOWN_SVC_STEMS["contact"] = "ts-contacts-service"
    # Common agent typos
    _KNOWN_SVC_NORMALIZED["nside_payment_service"] = "ts-inside-payment-service"
    _KNOWN_SVC_STEMS["nsidepayment"] = "ts-inside-payment-service"
    # rabbitmq ts- prefix variant (agents commonly write ts-rabbitmq)
    _KNOWN_SVC_NORMALIZED["rabbitmq"] = "rabbitmq"
    _KNOWN_SVC_STEMS["rabbitmq"] = "rabbitmq"
    # k8s DNS -svc suffix (agents sometimes use ts-xxx-svc instead of ts-xxx-service)
    # svc is the standard k8s DNS shorthand
    for svc in list(_KNOWN_SVC_NORMALIZED.values()):
        if svc.endswith("-service"):
            svc_abbr = svc.replace("-service", "-svc")
            _KNOWN_SVC_NORMALIZED[_normalize_service(svc_abbr)] = svc
            bare_svc = svc[3:-8] if svc.startswith("ts-") else svc
            _KNOWN_SVC_STEMS[bare_svc.replace("-", "") + "svc"] = svc


def resolve_known_service(candidate: str) -> str | None:
    """Resolve a candidate service name to a known canonical service.

    Tries: exact normalized match, then bare stem match, then prefix match.
    Returns canonical service name or None if not recognized.
    """
    norm = _normalize_service(candidate)
    if norm in _KNOWN_SVC_NORMALIZED:
        return _KNOWN_SVC_NORMALIZED[norm]
    # Try bare stem
    bare = candidate.lower()
    if bare.startswith("ts-"):
        bare = bare[3:]
    if bare.endswith("-service"):
        bare = bare[:-8]
    bare_joined = bare.replace("-", "")
    if bare_joined in _KNOWN_SVC_STEMS:
        return _KNOWN_SVC_STEMS[bare_joined]
    if bare in _KNOWN_SVC_STEMS:
        return _KNOWN_SVC_STEMS[bare]
    # Prefix match: "insidepay" is prefix of "insidepayment" -> ts-inside-payment-service
    # Only match if exactly one stem starts with our candidate (avoid ambiguity)
    if len(bare_joined) >= 5:
        prefix_matches = [v for k, v in _KNOWN_SVC_STEMS.items()
                          if k.startswith(bare_joined) and k != bare_joined]
        if len(prefix_matches) == 1:
            return prefix_matches[0]
    return None


# Pod name pattern: ts-food-service-5c7888968f-sv8t9 (service name + replicaset hash + pod hash)
# Also handles chaos-mesh injected fault-type middle segments and trailing "-pod" markers:
#   ts-seat-service-request-replace-path-qz6dc5 (fault: request-replace-path)
#   ts-preserve-service-pod-failure (bare "-pod-failure" marker, no hash)
#   ts-travel2-service-pod (bare "-pod" marker)
#   ts-rabbitmq-0 (StatefulSet ordinal)
_CHAOS_FAULT_TYPES = (
    r"(?:container-kill|pod-kill|pod-failure|request-abort|response-abort|"
    r"request-delay|response-delay|request-replace-method|request-replace-path|"
    r"response-replace-body|response-replace-code|response-patch-body|request-patch-body|"
    r"memory-stress|cpu-stress|stress|corrupt|exception|delay)"
)
_POD_NAME_PATTERN = re.compile(
    rf"^(ts-[a-z][-a-z0-9]*(?:-service|-mongo|-mysql|dashboard|rabbitmq))"
    rf"(?:-{_CHAOS_FAULT_TYPES})?"
    rf"(?:-[a-z0-9]{{4,}}[-a-z0-9]*|-pod|-\d+)?$"
)


_STATEFULSET_PATTERN = re.compile(r"^(?:ts-)?(rabbitmq|mysql|redis|mongodb|kafka|zookeeper|nacos)(?:-\d+)?$")


def _resolve_pod_name(candidate: str) -> str | None:
    """Try to extract a known service name from a K8s pod name or chaos injection pod.

    ts-food-service-5c7888968f-sv8t9 -> ts-food-service
    ts-ui-dashboard-5b4ff6488d-gvjbm -> ts-ui-dashboard
    ts-seat-service-request-replace-path-qz6dc5 -> ts-seat-service (chaos injection)
    ts-preserve-service-pod-failure -> ts-preserve-service (bare chaos marker)
    ts-rabbitmq-0 -> rabbitmq (StatefulSet ordinal)
    Returns resolved canonical service or None.
    """
    low = candidate.lower()
    # StatefulSet ordinals for infra services (rabbitmq-0, ts-rabbitmq-0, mysql-1, etc.)
    ss = _STATEFULSET_PATTERN.match(low)
    if ss:
        infra = ss.group(1)
        if infra in NON_TS_SERVICES:
            return infra
    m = _POD_NAME_PATTERN.match(low)
    if not m:
        return None
    svc_part = m.group(1)
    return resolve_known_service(svc_part)


# SQL LIKE pattern: service_name LIKE '%xxx%'
SQL_LIKE_PATTERN = re.compile(r"service_name\s+LIKE\s+['\"]%([^%'\"]+)%['\"]", re.IGNORECASE)

# message/span_name LIKE pattern: message LIKE '%cancelservice%', span_name LIKE '%travelplanservice%'
# Also handles multi-wildcard: '%routeservice%routes%' — captures first segment between %'s
MSG_LIKE_PATTERN = re.compile(r"(?:message|span_name)\s+LIKE\s+['\"]%([^%'\"]+)%", re.IGNORECASE)

# Noise words that shouldn't be treated as service stems
_NL_NOISE_STEMS = frozenset({
    # Articles & pronouns
    "the", "a", "an", "this", "that", "each", "every", "any", "some",
    "my", "our", "its", "one", "other", "same", "another",
    # Conjunctions & prepositions
    "and", "or", "to", "for", "of", "in", "on", "at", "by", "from", "with",
    "about", "between", "through", "than", "into", "after", "before", "during",
    # Verbs commonly preceding "service"
    "understand", "understanding", "check", "checking", "see", "seeing",
    "investigate", "investigating", "examine", "examining", "analyze", "analyzing",
    "trace", "tracing", "query", "querying", "find", "finding",
    "get", "getting", "show", "showing", "list", "listing", "view", "viewing",
    "look", "looking", "call", "calling", "test", "testing",
    "monitor", "monitoring", "access", "accessing", "request", "requesting",
    "fetch", "fetching", "identify", "identifying",
    "suggest", "suggesting", "suggests",
    "help", "helping", "let", "need", "want", "try", "start", "starting",
    "run", "running", "use", "using", "contain", "containing", "contains",
    "include", "including", "includes", "cause", "causing", "causes",
    "fail", "failing", "fails", "failed",
    "called", "calls", "indicate", "indicates", "build", "building",
    "enable", "enabling", "have", "having", "are", "were", "was", "been",
    "could", "would", "should", "may", "might", "will", "shall",
    "also", "even", "just", "only", "still", "already", "yet",
    # Generic nouns/adjectives
    "root", "cause", "key", "main", "primary", "data", "map",
    "type", "name", "all", "new", "first", "last", "next", "above",
    "downstream", "upstream", "backend", "frontend", "external", "internal",
    "individual", "specific", "affected", "target", "related", "available",
    "following", "mentioned", "relevant", "particular", "certain", "potential",
    "possible", "likely", "actual", "real", "missing", "different", "various",
    "full", "complete", "entire", "total", "overall", "earliest", "latest",
    "workload", "information", "detail", "details", "description", "summary",
    "abnormal", "normal", "services",
    "foundational", "explicit", "inter", "correlation", "calculation",
    "clues", "mapping", "earlier", "more", "multiple", "subsequent",
    "these", "those", "underlying", "unique",
    # Interrogative / pronoun
    "which", "what", "who", "where", "when", "why", "me", "we", "they",
    # Meta / telemetry words
    "service", "metric", "metrics", "log", "logs", "span", "spans", "endpoint",
    "trace", "traces", "tracing", "error", "errors", "timeout", "connection",
    "response", "status", "code", "http", "api", "url", "path",
    # Domain-specific noise (too generic to be service stems alone)
    "plan", "trip", "trips", "left", "right", "cheapest", "quickest",
    "min", "max", "minstation", "minstopstations",
    # Short filler
    "is", "if", "it", "no", "not", "so", "as", "be", "do", "up", "has", "had",
})

DATA_TYPE_KEYWORDS = {
    "logs": ["log", "logs", "logging"],
    "metrics": ["metric", "metrics", "gauge", "counter", "histogram"],
    "traces": ["trace", "traces", "span", "tracing"],
}


# ── Data Structures ─────────────────────────────────────────────────────────


@dataclass
class ServiceExtractionResult:
    """Result of service extraction with hallucination detection.

    services: validated service names (in whitelist or known infra)
    hallucinated: service-like names the agent used that don't exist in the system
    """

    services: list[str] = field(default_factory=list)
    hallucinated: list[str] = field(default_factory=list)


@dataclass
class ExtractedStep:
    """Structured information extracted from a single tool call."""

    step_index: int

    # From think_tool
    thought: str | None
    thought_services: list[str] = field(default_factory=list)
    thought_data_types: list[str] = field(default_factory=list)
    thought_hallucinated: list[str] = field(default_factory=list)

    # Which assistant turn this step came from (for parallel_fanout detection)
    assistant_turn_index: int = 0

    # From tool_call
    action_tool: str = ""
    action_sql: str = ""
    action_data_type: str = ""  # logs / metrics / traces / discovery / unknown
    action_intent: str = ""  # 19 troubleshooting intents (see intention_category.md):
    # Traces: latency_ranking / throughput_compare / error_rate_scan / service_trace_scan / trace_follow / call_tree_build
    # Logs: error_log_overview / service_error_log / service_log_browse / keyword_search / error_timeline
    # Metrics: metric_scan / container_resource / jvm_state / network_layer / k8s_state / db_state
    # Baseline: baseline_collect / baseline_contrast
    # Excluded (returned as "discovery"): schema_discovery (list_tables/get_schema), think_tool
    action_services: list[str] = field(default_factory=list)
    action_hallucinated: list[str] = field(default_factory=list)

    # From tool result
    result_content: str = ""
    result_is_error: bool = False
    result_services: list[str] = field(default_factory=list)
    result_hallucinated: list[str] = field(default_factory=list)

    @property
    def ngram_token(self) -> str:
        """Token for n-gram / Markov analysis. Uses intent directly since the
        19 troubleshooting intents already encode data source implicitly."""
        return self.action_intent


@dataclass
class GTContext:
    """Ground truth context derived from CausalGraph for path analysis."""

    path_services: set[str] = field(default_factory=set)
    root_cause_services: set[str] = field(default_factory=set)
    alarm_services: set[str] = field(default_factory=set)
    service_edges: set[tuple[str, str]] = field(default_factory=set)

    def is_on_path(self, service: str) -> bool:
        """Check if a service is on the causal path.

        Uses normalized comparison (strips ts- prefix, lowercases, replaces hyphens).
        Also handles fuzzy candidates: 'ts-preserve-service' matches if
        'ts-preserve-service' is in path, even when input is 'preserve service'.
        """
        normalized = _normalize_service(service)
        return any(_normalize_service(s) == normalized for s in self.path_services)

    def resolve_on_path(self, candidates: list[str]) -> list[str]:
        """From a list of candidate service names, return those that match GT path.

        Useful for fuzzy-extracted candidates where multiple forms may exist.
        """
        return [c for c in candidates if self.is_on_path(c)]

    def distance_to_root(self, service: str) -> int | None:
        """Shortest distance from service to any root cause in the causal graph.

        Returns None if service is not on path.
        Uses BFS on service_edges.
        """
        normalized = _normalize_service(service)

        # Build adjacency (reverse direction: target -> source, to find path to root)
        reverse_adj: dict[str, list[str]] = {}
        for src, tgt in self.service_edges:
            src_n = _normalize_service(src)
            tgt_n = _normalize_service(tgt)
            reverse_adj.setdefault(tgt_n, []).append(src_n)

        root_normalized = {_normalize_service(r) for r in self.root_cause_services}

        if normalized in root_normalized:
            return 0

        # BFS from service toward root
        visited = {normalized}
        queue = [(normalized, 0)]
        while queue:
            current, dist = queue.pop(0)
            for neighbor in reverse_adj.get(current, []):
                if neighbor in root_normalized:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        return None

    @classmethod
    def from_causal_graph(cls, graph: CausalGraph) -> "GTContext":
        path_services = graph.get_service_nodes()
        root_cause_services = graph.get_root_cause_services()
        alarm_services = graph.get_alarm_services()
        service_edges = graph.get_service_edges()
        return cls(
            path_services=path_services,
            root_cause_services=root_cause_services,
            alarm_services=alarm_services,
            service_edges=service_edges,
        )


# ── Service Extraction ───────────────────────────────────────────────────────


def _normalize_service(name: str) -> str:
    """Normalize service name for comparison.

    Strips ts- prefix and converts to lowercase with underscores,
    so 'ts-preserve-service' and 'preserve-service' both become 'preserve_service'.
    """
    lower = name.lower()
    if lower.startswith("ts-") or lower.startswith("ts_"):
        lower = lower[3:]
    return lower.replace("-", "_")


# Initialize known service lookups now that _normalize_service is defined
_init_known_service_lookups()


def _msg_like_to_ts_candidates(raw: str) -> list[str]:
    """Convert a message/span_name LIKE pattern value to candidate ts-* service names.

    Handles camelCase ('cancelService'), underscore ('inside_pay_service'),
    hyphenated ('ts-food-service'), and all-lowercase concatenated forms
    ('travelplanservice', 'preserveservice') found in message/span_name LIKE clauses.

    'cancelservice' -> ['ts-cancel-service', 'ts-cancel']
    'inside_pay_service' -> ['ts-inside-pay-service', 'ts-inside-pay']
    'travelplanservice' -> ['ts-travelplan-service', 'ts-travelplan'] (greedy split also tried)
    'preserveservice' -> ['ts-preserve-service', 'ts-preserve']
    """
    raw = raw.strip().lower()
    if not raw:
        return []

    # Already ts-* form
    if raw.startswith("ts-"):
        return [raw]

    # Strip trailing "service" if present
    stem = raw
    if stem.endswith("service"):
        stem = stem[:-7]  # remove "service"
    if stem.endswith("_"):
        stem = stem[:-1]
    if stem.endswith("-"):
        stem = stem[:-1]

    if not stem:
        return []

    # Split on underscores, hyphens, or camelCase boundaries
    if "_" in stem or "-" in stem:
        parts = re.split(r"[-_]+", stem)
    else:
        # Try camelCase split first
        camel_split = re.sub(r"([a-z])([A-Z])", r"\1-\2", stem).lower().split("-")
        if len(camel_split) > 1:
            parts = camel_split
        else:
            # All-lowercase concatenated: try greedy match against known service words
            parts = _greedy_split_service_stem(stem)

    # Don't filter against noise list here — these are actual service name parts
    # from SQL LIKE patterns, not natural language
    parts = [p for p in parts if p]
    if not parts:
        return []

    hyphenated = "-".join(parts)
    # Only generate -service form; bare ts-xxx is handled by exact SERVICE_PATTERN
    return [f"ts-{hyphenated}-service"]


# Common word parts in RCABench service names for greedy splitting
_SERVICE_WORD_PARTS = [
    "station", "travel", "preserve", "inside", "payment", "cancel",
    "config", "consign", "contacts", "route", "plan", "order", "other",
    "basic", "price", "food", "train", "seat", "auth", "user",
    "security", "verification", "code", "assurance", "ui", "dashboard",
]
# Sort longest first for greedy matching
_SERVICE_WORD_PARTS.sort(key=len, reverse=True)


def _greedy_split_service_stem(stem: str) -> list[str]:
    """Greedily split an all-lowercase concatenated stem into known service word parts.

    'travelplan' -> ['travel', 'plan']
    'insidepay' -> ['inside', 'pay'] (partial match: 'inside' + remaining 'pay')
    'preserve' -> ['preserve']
    'stationfood' -> ['station', 'food']
    'travel2' -> ['travel2'] (digit suffix stays attached)
    """
    if not stem:
        return []
    parts: list[str] = []
    remaining = stem
    while remaining:
        matched = False
        for word in _SERVICE_WORD_PARTS:
            if remaining.startswith(word):
                # If what remains after the word is just digits, merge them
                rest = remaining[len(word):]
                if rest and rest.isdigit():
                    parts.append(remaining)  # e.g., "travel2" as one part
                    remaining = ""
                else:
                    parts.append(word)
                    remaining = rest
                matched = True
                break
        if not matched:
            parts.append(remaining)
            break
    return parts


def _stem_to_ts_candidates(stem: str) -> list[str]:
    """Convert a natural language stem to candidate ts-* service names.

    Only generates ts-xxx-service form (not bare ts-xxx) to avoid false positives.
    The bare ts-xxx pattern is already covered by exact SERVICE_PATTERN matching.

    'preserve' -> ['ts-preserve-service']
    'travel plan' -> ['ts-travel-plan-service']
    'ui dashboard' -> ['ts-ui-dashboard-service']
    """
    stem = stem.lower().strip()
    if not stem:
        return []
    words = stem.replace("-", " ").replace("_", " ").split()
    if not words:
        return []
    # If ALL words are noise, reject entirely
    if all(w in _NL_NOISE_STEMS for w in words):
        return []
    # For single-word stems, apply noise filter (too ambiguous alone)
    if len(words) == 1 and words[0] in _NL_NOISE_STEMS:
        return []
    # Keep all words for multi-word stems (they form specific service names)
    hyphenated = "-".join(words)
    return [f"ts-{hyphenated}-service"]


def _validate_candidates(
    candidates: list[str],
    *,
    keep_unresolved: bool = False,
) -> ServiceExtractionResult:
    """Validate service candidates through whitelist, splitting into valid vs hallucinated.

    Args:
        candidates: raw candidate service names
        keep_unresolved: if True, keep unresolved ts-*-service names that have no NL noise
                         (for result content where agent inventions are meaningful)
    """
    valid: list[str] = []
    hallucinated: list[str] = []

    for s in candidates:
        if s.startswith("ts-ts-"):
            continue
        # Skip candidates with URL path chars or spaces (not valid service names)
        if "/" in s or " " in s:
            continue
        if s in NON_TS_SERVICES:
            valid.append(s)
            continue
        resolved = resolve_known_service(s)
        if resolved:
            if resolved not in valid:
                valid.append(resolved)
            continue
        pod_resolved = _resolve_pod_name(s)
        if pod_resolved:
            if pod_resolved not in valid:
                valid.append(pod_resolved)
            continue
        # Unresolved: classify as hallucination
        # Only count service-like patterns (not NL noise like "ts-through-the-service")
        if s.startswith("ts-"):
            is_nl_noise = False
            inner = s[3:]
            if inner.endswith("-service"):
                inner = inner[:-8]
            parts = inner.split("-")
            if any(p in _NL_NOISE_STEMS for p in parts):
                is_nl_noise = True
            if not is_nl_noise:
                hallucinated.append(s)
                if keep_unresolved:
                    valid.append(s)

    return ServiceExtractionResult(
        services=list(dict.fromkeys(valid)),
        hallucinated=list(dict.fromkeys(hallucinated)),
    )


def _collect_text_candidates(text: str) -> list[str]:
    """Collect all service name candidates from text (before whitelist validation)."""
    services: list[str] = []

    # 1. Exact ts-* matches (highest priority)
    services.extend(SERVICE_PATTERN.findall(text))

    # 2. Natural language: "xxx service" -> ts-xxx-service candidates
    #    Try 3-word, 2-word, then 1-word stems; longer stems take priority
    #    Skip if the match position is inside an already-extracted ts-* name
    exact_ts_normalized = {_normalize_service(s) for s in services}
    seen_stems: set[str] = set()
    for pattern in (NL_SERVICE_3W, NL_SERVICE_2W, NL_SERVICE_1W):
        for m in pattern.finditer(text):
            # Skip if this "xxx service" is part of "ts-xxx-service" already in text
            # Check preceding chars for "ts-" (possibly with markdown: **ts- or `ts-)
            start = m.start()
            prefix_check = text[max(0, start - 6):start].lower()
            if "ts-" in prefix_check:
                continue
            raw_stem = m.group(1).lower().replace("-", " ")
            # Drop leading noise words
            words = raw_stem.split()
            while words and words[0] in _NL_NOISE_STEMS:
                words.pop(0)
            if not words or all(w in _NL_NOISE_STEMS for w in words):
                continue
            stem = " ".join(words)
            if stem not in seen_stems:
                seen_stems.add(stem)
                candidates = _stem_to_ts_candidates(stem)
                # Don't add candidates that duplicate already-extracted services (by normalization)
                for c in candidates:
                    c_norm = _normalize_service(c)
                    if c_norm not in exact_ts_normalized:
                        services.append(c)
                        exact_ts_normalized.add(c_norm)

    # 3. No-prefix: "preserve-service" -> "ts-preserve-service"
    # Refresh normalized set after NL additions
    all_normalized = {_normalize_service(s) for s in services}
    for m in NO_PREFIX_SERVICE_PATTERN.finditer(text):
        matched = m.group(1)
        # Skip if the match itself starts with ts- (regex captured whole ts-xxx-service)
        if matched.lower().startswith("ts-"):
            continue
        # Skip if preceded by "ts-" (markdown: **ts- or `ts-)
        start = m.start()
        prefix = text[max(0, start - 5):start].lower()
        if "ts-" in prefix:
            continue
        candidate = f"ts-{matched}"
        # Skip if normalization matches an already-extracted service
        if _normalize_service(candidate) not in all_normalized:
            services.append(candidate)
            all_normalized.add(_normalize_service(candidate))

    # 4. Known non-ts services
    text_lower = text.lower()
    for svc in NON_TS_SERVICES:
        if svc in text_lower:
            services.append(svc)

    # 5. URL path service names: /api/v1/preserveservice/...
    #    Only extract the first path segment after /api/v1/ that ends with "service"
    #    e.g., /api/v1/travelplanservice/travelPlan/minStation -> travelplanservice
    for m in re.finditer(r"/api/v\d+/([a-z][a-z0-9]*service)\b", text, re.IGNORECASE):
        url_svc = m.group(1).lower()
        candidates = _msg_like_to_ts_candidates(url_svc)
        for c in candidates:
            norm = _normalize_service(c)
            if norm not in all_normalized:
                services.append(c)
                all_normalized.add(norm)

    # 6. Bare stem scanning: find known service stems in text without "service" suffix
    #    e.g., "preserve endpoint", "the travel related", "cancel operation"
    #    Only match stems that are known service names to avoid false positives
    for bare_stem, canonical in _KNOWN_SVC_STEMS.items():
        if bare_stem in NON_TS_SERVICES:
            continue  # Already handled in step 4
        if len(bare_stem) < 4:
            continue  # Skip very short stems ("ui", "auth") — too many false positives
        # Search for the bare stem as a whole word in text
        if re.search(rf"\b{re.escape(bare_stem)}\b", text_lower):
            norm = _normalize_service(canonical)
            if norm not in all_normalized:
                services.append(canonical)
                all_normalized.add(norm)

    return services


def extract_services_from_text(text: str) -> list[str]:
    """Extract service names from text using exact and fuzzy patterns.

    Handles:
    1. Exact ts-* pattern: 'ts-preserve-service'
    2. Natural language: 'preserve service', 'travel plan service'
    3. No-prefix: 'preserve-service' (without ts-)
    4. Known non-ts services: 'loadgenerator', 'mysql'
    5. URL path service names: '/api/v1/preserveservice/...'
    6. Bare stem scanning against known vocabulary
    """
    if not text:
        return []
    return _validate_candidates(_collect_text_candidates(text)).services


def extract_services_from_text_with_hallucination(text: str) -> ServiceExtractionResult:
    """Same as extract_services_from_text but also returns hallucinated service names."""
    if not text:
        return ServiceExtractionResult()
    return _validate_candidates(_collect_text_candidates(text))


def _collect_sql_candidates(sql: str) -> list[str]:
    """Collect service name candidates from SQL WHERE clauses (before validation).

    Handles:
    1. Exact match: service_name = 'ts-xxx'
    2. IN clause: service_name IN ('ts-xxx', 'ts-yyy')
    3. LIKE pattern: service_name LIKE '%xxx%' -> ts-xxx-service candidates
    4. Non-ts exact match: service_name = 'loadgenerator'
    5. URL-style service refs in span_name/message LIKE
    """
    nodes: list[str] = []

    # 1. WHERE service_name = 'xxx' or service_name != 'xxx'
    for m in re.finditer(r"service_name\s*[!=]+\s*['\"]([^'\"]+)['\"]", sql, re.IGNORECASE):
        val = m.group(1)
        # Strip URL path suffix: 'ts-order-service/order/refresh' -> 'ts-order-service'
        if "/" in val:
            val = val.split("/")[0]
        if val.startswith("ts-"):
            nodes.append(val)
        elif val.lower() in NON_TS_SERVICES:
            nodes.append(val.lower())

    # 2. WHERE service_name IN ('ts-xxx', 'ts-yyy')
    for m in re.finditer(r"service_name\s+IN\s*\(([^)]+)\)", sql, re.IGNORECASE):
        for val in re.split(r"[,\s]+", m.group(1)):
            val = val.strip("'\" ")
            if "/" in val:
                val = val.split("/")[0]
            if val.startswith("ts-"):
                nodes.append(val)
            elif val.lower() in NON_TS_SERVICES:
                nodes.append(val.lower())

    # 3. LIKE pattern: service_name LIKE '%cancel%' -> ts-cancel-service, ts-cancel
    for m in SQL_LIKE_PATTERN.finditer(sql):
        stem = m.group(1).lower().strip()
        if stem:
            nodes.extend(_stem_to_ts_candidates(stem))

    # 4. message/span_name LIKE patterns: '%cancelservice%', '%inside_pay_service%'
    for m in MSG_LIKE_PATTERN.finditer(sql):
        raw = m.group(1).strip()
        if not raw:
            continue
        raw_lower = raw.lower()
        if "service" in raw_lower:
            nodes.extend(_msg_like_to_ts_candidates(raw))
        elif raw_lower in NON_TS_SERVICES:
            nodes.append(raw_lower)

    # 5. URL-style service refs: '%orderservice/order/refresh%'
    for m in re.finditer(
        r"(?:span_name|message)\s+(?:LIKE|=)\s+['\"]%?[^'\"]*?([a-z][a-z0-9]*service)/",
        sql,
        re.IGNORECASE,
    ):
        nodes.extend(_msg_like_to_ts_candidates(m.group(1).lower()))

    return nodes


def extract_services_from_sql(sql: str) -> list[str]:
    """Extract validated service names from SQL WHERE clauses."""
    if not sql:
        return []
    return _validate_candidates(_collect_sql_candidates(sql)).services


def extract_services_from_sql_with_hallucination(sql: str) -> ServiceExtractionResult:
    """Same as extract_services_from_sql but also returns hallucinated service names."""
    if not sql:
        return ServiceExtractionResult()
    return _validate_candidates(_collect_sql_candidates(sql))


def _collect_result_candidates(content: str) -> list[str]:
    """Collect service name candidates from tool result content (before validation).

    Handles:
    1. JSON field: "service_name": "ts-xxx" or "service_name": "loadgenerator"
    2. Bare ts-* mentions in text
    3. Known non-ts services from JSON fields
    4. URL path service names: /api/v1/orderservice/...
    5. Known service compound stems: "foodservice endpoints", "preserveservice/preserve"
    6. Known infra services as bare words
    """
    services: list[str] = []

    # 1. JSON field pattern - accept ts-*, known non-ts services, and aliases
    for m in re.findall(r'"service_name"\s*:\s*"([^"]+)"', content):
        if m.startswith("ts-"):
            services.append(m)
        elif m.lower() in NON_TS_SERVICES:
            services.append(m.lower())
        elif m.lower() in RESULT_SERVICE_ALIASES:
            services.append(RESULT_SERVICE_ALIASES[m.lower()])

    # 2. Bare ts-* mentions
    services.extend(SERVICE_PATTERN.findall(content))

    # 3. URL path service names: /api/v1/preserveservice/preserve
    for m in re.finditer(r"/api/v\d+/([a-z][a-z0-9]*service)\b", content, re.IGNORECASE):
        url_svc = m.group(1).lower()
        services.extend(_msg_like_to_ts_candidates(url_svc))

    # 4. Compound stems as whole words: "foodservice", "orderservice", "preserveservice"
    content_lower = content.lower()
    all_normalized = {_normalize_service(s) for s in services}
    for stem, canonical in _KNOWN_SVC_STEMS.items():
        if not stem.endswith("service"):
            continue
        if len(stem) < 8:
            continue
        if re.search(rf"\b{re.escape(stem)}\b", content_lower):
            norm = _normalize_service(canonical)
            if norm not in all_normalized:
                services.append(canonical)
                all_normalized.add(norm)

    # 5. Known infra services as bare words
    for svc in NON_TS_SERVICES:
        if svc in content_lower and _normalize_service(svc) not in all_normalized:
            services.append(svc)
            all_normalized.add(_normalize_service(svc))

    return services


def extract_services_from_result(content: str) -> list[str]:
    """Extract validated service names from tool result content."""
    if not content:
        return []
    return _validate_candidates(_collect_result_candidates(content), keep_unresolved=True).services


def extract_services_from_result_with_hallucination(content: str) -> ServiceExtractionResult:
    """Extract service names from result content with hallucination detection."""
    if not content:
        return ServiceExtractionResult()
    return _validate_candidates(_collect_result_candidates(content), keep_unresolved=True)


# ── Data Type Classification ─────────────────────────────────────────────────


def classify_data_type(tool_name: str, args: dict) -> str:
    """Classify the data type being queried."""
    if tool_name in ("list_tables_in_directory", "get_schema"):
        return "discovery"
    target = args.get("parquet_files") or args.get("parquet_file") or ""
    if isinstance(target, list):
        target = " ".join(target)
    target = target.lower()
    if "log" in target:
        return "logs"
    if "metric" in target:
        return "metrics"
    if "trace" in target:
        return "traces"
    return "unknown"


def extract_data_types_from_text(text: str) -> list[str]:
    """Extract mentioned data type keywords from text."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for dtype, keywords in DATA_TYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(dtype)
    return found


# ── Query Intent Classification ──────────────────────────────────────────────


def classify_intent(tool_name: str, sql: str) -> str:
    """Classify query intent into 19 troubleshooting-oriented categories.

    Designed for Markov state matrix analysis. Categories align with:
      1. Necessary diagnostic actions for each fault type
      2. Real human SRE troubleshooting actions

    Priority order (first match wins) — most distinctive signal first:
      P1 structural: call_tree_build > baseline_contrast
      P2 table:      baseline_collect
      P3 id-scope:   trace_follow
      P4 analytical:  error_timeline
      P5 metric-domain: network_layer > jvm_state > k8s_state > db_state > container_resource
      P5.5 metric-scan: metric_scan
      P6 text-search: keyword_search
      P7 log-analysis: service_error_log > service_log_browse > error_log_overview
      P8 trace-analysis: error_rate_scan > service_trace_scan > throughput_compare > latency_ranking

    schema_discovery (list_tables/get_schema) and think_tool are excluded from
    the 19 intents — they appear in every trajectory and carry no diagnostic signal.
    They are returned as "discovery" for backward compatibility but should be
    filtered out before Markov / n-gram analysis.

    See intention_category.md for full documentation.
    """
    # ── Excluded: schema discovery & think ──
    if tool_name in ("list_tables_in_directory", "get_schema"):
        return "discovery"
    if not sql:
        return "discovery"

    sql_upper = sql.upper().strip()
    sql_upper = re.sub(r"\s+", " ", sql_upper)

    has_abnormal = "ABNORMAL_" in sql_upper
    has_normal = bool(re.search(r"(?<!AB)NORMAL_", sql_upper))

    # ── P1: Structural uniqueness ──
    # call_tree_build: JOIN parent_span_id = span_id
    if re.search(
        r"PARENT_SPAN_ID\s*=\s*\w*\.?SPAN_ID|\w*\.?SPAN_ID\s*=\s*\w*\.?PARENT_SPAN_ID",
        sql_upper,
    ):
        return "call_tree_build"

    # baseline_contrast: comparing normal + abnormal tables
    #   - UNION normal + abnormal (side-by-side comparison)
    #   - EXCEPT / INTERSECT normal vs abnormal (set difference)
    #   - JOIN normal + abnormal (cross-period correlation)
    if has_normal and has_abnormal:
        return "baseline_contrast"

    # ── P2: Table uniqueness ──
    # baseline_collect: only normal_* tables (building baseline)
    if has_normal and not has_abnormal:
        return "baseline_collect"

    # ── Extract WHERE clause for subsequent checks ──
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bUNION\b|$)", sql_upper, re.DOTALL)
    where_clause = wm.group(1) if wm else ""

    # ── P3: ID-level scope ──
    # trace_follow: WHERE trace_id = (single request call chain)
    if re.search(r"TRACE_ID\s*(=|IN)", where_clause):
        return "trace_follow"

    # ── P4: Analytical uniqueness ──
    # error_timeline: MIN(time)/MAX(time) GROUP BY (who errored first?)
    sel_match = re.search(r"SELECT\s+(.*?)(?:\bFROM\b|$)", sql_upper, re.DOTALL)
    select_clause = sel_match.group(1) if sel_match else ""
    if re.search(r"(MIN|MAX)\s*\(\s*TIME", select_clause) and "GROUP BY" in sql_upper:
        return "error_timeline"

    # ── P5: Metric domain (by metric name — precise or LIKE) ──
    has_metrics_table = bool(re.search(r"(?:ABNORMAL_|NORMAL_)?METRICS", sql_upper))

    if has_metrics_table:
        # Build search context from WHERE clause + full SQL (catches LIKE patterns)
        metric_ctx = where_clause + " " + sql_upper

        # network_layer: hubble / http request / network / tcp / drop
        if any(kw in metric_ctx for kw in (
            "HUBBLE", "HTTP_REQUEST", "HTTP.SERVER", "HTTP.CLIENT",
            "NETWORK", "TCP", "DROP", "RETRANSMIT", "PACKET",
        )):
            return "network_layer"
        if re.search(r"LIKE\s*'%?(?:NETWORK|NET|HTTP|DROP|TCP|LOSS|LATENCY|HUBBLE)", metric_ctx):
            return "network_layer"

        # jvm_state: jvm / gc / queue / hikari / thread / heap
        if any(kw in metric_ctx for kw in (
            "JVM.", "JVM%", "GC.", "QUEUESIZE", "HIKARI", "THREAD", "HEAP",
        )):
            return "jvm_state"
        if re.search(r"LIKE\s*'%?(?:JVM|GC|THREAD|QUEUE|HEAP|HIKARI)", metric_ctx):
            return "jvm_state"

        # k8s_state: deployment / restart / pod phase / kill
        if any(kw in metric_ctx for kw in (
            "K8S.DEPLOYMENT", "K8S.REPLICASET", "RESTART",
            "POD.PHASE", "POD-KILL", "POD_KILL",
            "CONTAINER-KILL", "CONTAINER_KILL",
            "K8S.CONTAINER.READY", "TERMINATED", "EVICT",
        )):
            return "k8s_state"
        if re.search(r"LIKE\s*'%?(?:RESTART|KILL|PHASE|READY|TERMINAT|EVICT|DEPLOY|POD)", metric_ctx):
            return "k8s_state"

        # db_state: db.client / mysql / connections
        if any(kw in metric_ctx for kw in ("DB.CLIENT", "MYSQL")):
            return "db_state"
        if "CONNECTIONS" in metric_ctx:
            return "db_state"
        if re.search(r"LIKE\s*'%?(?:DB|MYSQL|CONN)", metric_ctx):
            return "db_state"

        # container_resource: container.cpu / memory / filesystem / k8s.pod.cpu / memory
        if any(kw in metric_ctx for kw in (
            "CONTAINER.CPU", "CONTAINER.MEMORY", "CONTAINER.FILESYSTEM",
            "K8S.POD.CPU", "K8S.POD.MEMORY", "K8S.POD.FILESYSTEM",
            "CPU_LIMIT", "MEMORY_LIMIT",
            "CONTAINER.MEMORY.RSS", "CONTAINER.MEMORY.WORKING_SET",
            "K8S.POD.CPU.NODE", "K8S.POD.MEMORY.NODE",
            "CPU.USAGE", "MEMORY.USAGE", "CPU.UTILIZATION", "MEMORY.AVAILABLE",
        )):
            return "container_resource"
        if re.search(r"LIKE\s*'%?(?:CPU|MEMORY|MEM|OOM|FILESYSTEM|DISK)", metric_ctx):
            return "container_resource"

        # Fallback: check metric values in WHERE for unmatched keywords
        for mv in re.findall(r"METRIC\s*(?:=|LIKE|IN)\s*['\(]([^'\)]+)", sql_upper):
            mv_up = mv.upper()
            if any(kw in mv_up for kw in ("CPU", "MEMORY", "MEM", "FILESYSTEM", "OOM", "DISK")):
                return "container_resource"
            if any(kw in mv_up for kw in ("NETWORK", "NET", "HTTP", "DROP", "TCP", "HUBBLE", "LATENCY")):
                return "network_layer"
            if any(kw in mv_up for kw in ("JVM", "GC", "THREAD", "QUEUE", "HEAP")):
                return "jvm_state"
            if any(kw in mv_up for kw in ("RESTART", "KILL", "PHASE", "DEPLOY", "POD", "READY")):
                return "k8s_state"
            if any(kw in mv_up for kw in ("DB", "MYSQL", "CONN")):
                return "db_state"

        # ── P5.5: metric_scan — no specific metric → exploring what's available ──
        if "DISTINCT" in sql_upper and "METRIC" in select_clause:
            return "metric_scan"
        if not re.search(r"\bMETRIC\s*(=|IN|LIKE)", where_clause):
            return "metric_scan"

        # Remaining metrics with unrecognized metric name → default to container_resource
        return "container_resource"

    # ── P6: Text search ──
    # keyword_search: LIKE on message/span_name
    if re.search(r"(MESSAGE|SPAN_NAME)\s*LIKE", sql_upper):
        return "keyword_search"

    # ── P7: Log analysis ──
    has_logs_table = bool(re.search(r"(?:ABNORMAL_|NORMAL_)?LOGS", sql_upper))
    has_svc_filter = bool(re.search(r"SERVICE_NAME\s*(=|IN|LIKE)", where_clause))
    has_level_filter = bool(re.search(r"\bLEVEL\s*(=|IN)", where_clause))

    if has_logs_table:
        if has_svc_filter and has_level_filter:
            return "service_error_log"
        if has_svc_filter:
            return "service_log_browse"
        return "error_log_overview"

    # ── P8: Trace analysis ──
    has_status_code = bool(re.search(r"STATUS_CODE", sql_upper))
    has_group_by = "GROUP BY" in sql_upper
    has_avg_duration = bool(re.search(r"AVG\s*\(\s*DURATION", sql_upper))
    has_count = "COUNT(" in sql_upper

    if has_status_code:
        return "error_rate_scan"
    if has_svc_filter and has_group_by:
        return "service_trace_scan"
    if has_svc_filter:
        return "service_trace_scan"
    if has_count and has_group_by and not has_avg_duration:
        return "throughput_compare"

    # latency_ranking: traces GROUP BY service AVG(duration) — fallback
    return "latency_ranking"


# ── Thought Merging ──────────────────────────────────────────────────────────


def _merge_thoughts(existing: str | None, new: str) -> str:
    """Merge a new thought fragment into the existing pending thought."""
    if not existing:
        return new
    return f"{existing}\n\n{new}"


# ── Trajectory Parsing ───────────────────────────────────────────────────────


def _parse_openai_messages(messages: list[dict]) -> list[ExtractedStep]:
    """Parse OpenAI-format messages into ExtractedSteps."""
    # Build tool_call_id -> result mapping
    results_by_id: dict[str, dict] = {}
    for msg in messages:
        if msg.get("role") == "tool":
            content = str(msg.get("content") or "")
            is_error = "error" in content.lower() and ("Error" in content or '"error"' in content)
            results_by_id[msg.get("tool_call_id", "")] = {
                "content": content,
                "is_error": is_error,
            }

    steps: list[ExtractedStep] = []
    pending_thought: str | None = None
    step_idx = 1
    turn_idx = 0  # increments for each assistant message that issues tool_calls

    for msg in messages:
        if msg.get("role") != "assistant":
            continue

        tool_calls = msg.get("tool_calls") or []
        msg_content = (msg.get("content") or "").strip()

        # Assistant message with content but no tool_calls: accumulate as thought
        if not tool_calls:
            if msg_content:
                pending_thought = _merge_thoughts(pending_thought, msg_content)
            continue

        turn_idx += 1

        # Check for implicit thought in message content field
        # (agent reasons in content before issuing tool calls)
        if msg_content:
            pending_thought = _merge_thoughts(pending_thought, msg_content)

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {}
            call_id = tc.get("id", "")

            if tool_name == "think_tool":
                # Explicit think_tool: merge reflection into pending thought
                reflection = args.get("reflection", "")
                if reflection:
                    pending_thought = _merge_thoughts(pending_thought, reflection)
                continue

            # Real action
            sql = args.get("query", "")
            result_data = results_by_id.get(call_id, {"content": "", "is_error": False})

            # Extract services with hallucination detection
            thought_ext = extract_services_from_text_with_hallucination(pending_thought) if pending_thought else ServiceExtractionResult()
            action_ext = extract_services_from_sql_with_hallucination(sql)
            result_ext = extract_services_from_result_with_hallucination(result_data["content"])

            step = ExtractedStep(
                step_index=step_idx,
                assistant_turn_index=turn_idx,
                thought=pending_thought,
                thought_services=thought_ext.services,
                thought_data_types=extract_data_types_from_text(pending_thought) if pending_thought else [],
                thought_hallucinated=thought_ext.hallucinated,
                action_tool=tool_name,
                action_sql=sql,
                action_data_type=classify_data_type(tool_name, args),
                action_intent=classify_intent(tool_name, sql),
                action_services=action_ext.services,
                action_hallucinated=action_ext.hallucinated,
                result_content=result_data["content"],
                result_is_error=result_data["is_error"],
                result_services=result_ext.services,
                result_hallucinated=result_ext.hallucinated,
            )
            steps.append(step)
            step_idx += 1
            pending_thought = None

    return steps


def _parse_langgraph_steps(data: list[dict]) -> list[ExtractedStep]:
    """Parse LangGraph step/action/observation format into ExtractedSteps.

    This format stores the entire conversation as flat text in the observation field.
    We extract SQL queries and parquet file references from the text.
    """
    steps: list[ExtractedStep] = []
    step_idx = 1

    for item in data:
        obs = item.get("observation", "")
        if not obs:
            continue

        # Extract SQL queries with their preceding parquet file context
        # Pattern: tool call with parquet_files followed by SQL query
        # We look for query_parquet_files calls in the text
        sql_blocks = re.findall(
            r"(?:parquet_files?[\"']?\s*[:=]\s*[\"']?([^\n\"']+\.parquet)[\"']?.*?)?"
            r"(?:query[\"']?\s*[:=]\s*[\"']?(SELECT\s+.+?)(?:[\"']\s*[,}]|\Z))",
            obs,
            re.IGNORECASE | re.DOTALL,
        )

        # Simpler approach: find all SQL SELECT statements
        sql_pattern = re.compile(r"(SELECT\s+.+?)(?:\n\n|\Z)", re.IGNORECASE | re.DOTALL)
        sqls = sql_pattern.findall(obs)

        # Find all parquet file references in order
        pf_pattern = re.compile(r"([\w/.-]*(?:normal|abnormal)[\w/.-]*\.parquet)", re.IGNORECASE)
        parquet_refs = pf_pattern.findall(obs)

        if not sqls:
            # No SQL found - might be discovery step
            if any(kw in obs.lower() for kw in ("filename", "row_count", "column_count")):
                result_ext = extract_services_from_result_with_hallucination(obs)
                step = ExtractedStep(
                    step_index=step_idx,
                    thought=None,
                    action_tool="list_tables_in_directory",
                    action_data_type="discovery",
                    action_intent="discovery",
                    result_content=obs[:2000],
                    result_services=result_ext.services,
                    result_hallucinated=result_ext.hallucinated,
                )
                steps.append(step)
                step_idx += 1
            continue

        for sql in sqls:
            # Clean up SQL
            sql_clean = sql.strip().rstrip("\"',}")

            # Determine data type from nearby parquet references
            data_type = "unknown"
            sql_lower = sql_clean.lower()
            for pf in parquet_refs:
                pf_lower = pf.lower()
                if "log" in pf_lower:
                    data_type = "logs"
                    break
                elif "metric" in pf_lower:
                    data_type = "metrics"
                    break
                elif "trace" in pf_lower:
                    data_type = "traces"
                    break
            # Also check table names in SQL
            if data_type == "unknown":
                if "log" in sql_lower:
                    data_type = "logs"
                elif "metric" in sql_lower:
                    data_type = "metrics"
                elif "trace" in sql_lower:
                    data_type = "traces"

            action_ext = extract_services_from_sql_with_hallucination(sql_clean)
            result_ext = extract_services_from_result_with_hallucination(obs)

            step = ExtractedStep(
                step_index=step_idx,
                thought=None,  # LangGraph step format doesn't separate think_tool
                action_tool="query_parquet_files",
                action_sql=sql_clean,
                action_data_type=data_type,
                action_intent=classify_intent("query_parquet_files", sql_clean),
                action_services=action_ext.services,
                action_hallucinated=action_ext.hallucinated,
                result_content="",  # Can't separate result from observation in flat format
                result_services=result_ext.services,
                result_hallucinated=result_ext.hallucinated,
            )
            steps.append(step)
            step_idx += 1

    return steps


def extract_steps(raw_trajectories: str | list) -> list[ExtractedStep]:
    """Extract structured steps from trajectory data.

    Supports multiple formats:
    1. OpenAI message format: [{role, content, tool_calls}, ...]
    2. Multi-agent format: [{agent, trajectory: [openai messages]}, ...]
    3. LangGraph step format: [{step, action, observation}, ...]
    """
    if isinstance(raw_trajectories, str):
        try:
            data = json.loads(raw_trajectories)
        except json.JSONDecodeError:
            return []
    else:
        data = raw_trajectories

    if not isinstance(data, list) or len(data) == 0:
        return []

    first = data[0]
    if not isinstance(first, dict):
        return []

    # Detect format
    if "role" in first:
        # OpenAI message format
        return _parse_openai_messages(data)
    elif "agent" in first and "trajectory" in first:
        # Multi-agent format: [{agent, trajectory: [messages]}]
        all_steps: list[ExtractedStep] = []
        for agent_data in data:
            traj = agent_data.get("trajectory", [])
            if isinstance(traj, list):
                all_steps.extend(_parse_openai_messages(traj))
        return all_steps
    elif "step" in first:
        # LangGraph step format
        return _parse_langgraph_steps(data)

    return []
