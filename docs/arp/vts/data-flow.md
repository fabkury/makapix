# VTS Data Flow

This document describes the end-to-end flow of view data through the View Tracking System, from initial capture to final presentation.

## High-Level Flow

```mermaid
flowchart LR
    subgraph Capture
        A[View Detected]
    end
    
    subgraph Enrichment
        B[Extract Metadata]
    end
    
    subgraph Queue
        C[Celery Task]
    end
    
    subgraph Storage
        D[(Database)]
    end
    
    subgraph Aggregation
        E[Daily Rollup]
    end
    
    subgraph Presentation
        F[Stats API]
    end
    
    A --> B --> C --> D --> E --> F
```

## Detailed Flow by Source

### Web Browser Flow

```mermaid
sequenceDiagram
    participant Browser
    participant API as FastAPI
    participant Celery
    participant Redis
    participant DB as PostgreSQL
    
    Browser->>API: GET /api/p/{sqid}
    Note over API: Extract metadata
    API->>API: hash_ip(client_ip)
    API->>API: detect_device_type(user_agent)
    API->>API: get_country_code(ip)
    API->>Celery: write_view_event.delay(event_data)
    API-->>Browser: Post data (200 OK)
    
    Note over Celery: Async processing
    Celery->>DB: INSERT INTO view_events
    
    Note over Browser: Later, user views stats
    Browser->>API: GET /api/post/{id}/stats
    API->>Redis: cache_get("post_stats:{id}")
    
    alt Cache Hit
        Redis-->>API: cached stats
    else Cache Miss
        API->>DB: Query view_events + post_stats_daily
        API->>API: Compute PostStats
        API->>Redis: cache_set("post_stats:{id}", stats, ttl=300)
    end
    
    API-->>Browser: PostStatsResponse
```

### Player Flow (Request/Response Pattern)

```mermaid
sequenceDiagram
    participant Player as p3a Player
    participant MQTT as MQTT Broker
    participant API as API Server
    participant Celery
    participant Redis
    participant DB as PostgreSQL
    
    Player->>MQTT: PUBLISH makapix/player/{key}/request/{req_id}<br/>{"request_type": "submit_view", ...}
    MQTT->>API: Message delivered
    
    Note over API: Authenticate player
    API->>DB: Query player by key
    
    Note over API: Rate limit check
    API->>Redis: EXISTS ratelimit:player_view:{key}
    
    alt Rate Limited
        API->>MQTT: PUBLISH response<br/>{"error": "rate_limited", "retry_after": N}
        MQTT-->>Player: Rate limit response
    else Allowed
        API->>Redis: SETEX ratelimit:player_view:{key} 5 "1"
        API->>Celery: write_view_event.delay(event_data)
        API->>MQTT: PUBLISH response<br/>{"success": true}
        MQTT-->>Player: Success response
    end
    
    Celery->>DB: INSERT INTO view_events
```

### Player Flow (Fire-and-Forget Pattern)

```mermaid
sequenceDiagram
    participant Player as p3a Player
    participant MQTT as MQTT Broker
    participant API as API Server
    participant Redis
    participant Celery
    participant DB as PostgreSQL
    
    Player->>MQTT: PUBLISH makapix/player/{key}/view<br/>(QoS 1, no response expected)
    MQTT->>API: Message delivered
    
    Note over API: Validate payload
    API->>API: Parse P3AViewEvent
    
    Note over API: Authenticate player
    API->>DB: Query player by key
    
    Note over API: Deduplication check
    API->>Redis: EXISTS view_dedup:{key}:{post_id}:{timestamp}
    
    alt Duplicate
        Note over API: Silently discard
    else Unique
        API->>Redis: SETEX view_dedup:{...} 60 "1"
        
        Note over API: Rate limit check
        API->>Redis: EXISTS ratelimit:player_view:{key}
        
        alt Rate Limited
            Note over API: Silently discard
        else Allowed
            API->>Redis: SETEX ratelimit:player_view:{key} 5 "1"
            API->>Celery: write_view_event.delay(event_data)
        end
    end
    
    Celery->>DB: INSERT INTO view_events
    
    Note over Player: No response expected
```

## Metadata Extraction

When a view is captured, the following metadata is extracted:

```mermaid
flowchart TD
    REQ[HTTP Request / MQTT Message]
    
    REQ --> IP[Client IP]
    REQ --> UA[User-Agent]
    REQ --> REF[Referer Header]
    REQ --> USER[Auth Token]
    
    IP --> |X-Forwarded-For| CLIENT_IP[Resolved IP]
    CLIENT_IP --> |SHA256| IP_HASH[viewer_ip_hash]
    CLIENT_IP --> |GeoIP Lookup| COUNTRY[country_code]
    
    UA --> |Regex Match| DEVICE[device_type]
    UA --> |SHA256| UA_HASH[user_agent_hash]
    
    REF --> |URL Parse| DOMAIN[referrer_domain]
    
    USER --> |Decode JWT| USER_ID[viewer_user_id]
    
    subgraph Output["View Event Data"]
        IP_HASH
        COUNTRY
        DEVICE
        UA_HASH
        DOMAIN
        USER_ID
    end
```

### Device Detection Logic

```mermaid
flowchart TD
    UA[User-Agent String]
    
    UA --> P{Makapix-Player?}
    P -->|Yes| PLAYER[device_type: player]
    
    P -->|No| T{iPad/Android Tablet?}
    T -->|Yes| TABLET[device_type: tablet]
    
    T -->|No| M{iPhone/Android Mobile?}
    M -->|Yes| MOBILE[device_type: mobile]
    
    M -->|No| DESKTOP[device_type: desktop]
```

## Daily Aggregation Flow

The daily rollup task runs once per day to aggregate old view events:

```mermaid
flowchart TD
    START[Celery Beat: rollup_view_events]
    
    START --> CUTOFF[Calculate cutoff: now - 7 days]
    CUTOFF --> COUNT[Count events older than cutoff]
    
    COUNT --> CHECK{Events > 0?}
    CHECK -->|No| DONE[Done - nothing to process]
    
    CHECK -->|Yes| BATCH[Process in batches of 10,000]
    
    BATCH --> AGG[Aggregate by post_id + date]
    
    subgraph Aggregation
        AGG --> TV[total_views++]
        AGG --> UV[unique IP hashes → set]
        AGG --> BC[views_by_country map]
        AGG --> BD[views_by_device map]
        AGG --> BT[views_by_type map]
    end
    
    AGG --> UPSERT{Record exists?}
    UPSERT -->|Yes| MERGE[Merge with existing]
    UPSERT -->|No| INSERT[Insert new record]
    
    MERGE --> DELETE[Delete old raw events]
    INSERT --> DELETE
    
    DELETE --> DONE2[Done]
```

## Statistics Computation Flow

On-demand statistics are computed by combining recent raw events with historical daily aggregates:

```mermaid
flowchart TD
    REQ[GET /api/post/{id}/stats]
    
    REQ --> AUTH[Verify authorization]
    AUTH --> CACHE{Redis cache hit?}
    
    CACHE -->|Yes| RETURN[Return cached stats]
    
    CACHE -->|No| COMPUTE[Compute fresh stats]
    
    subgraph Computation["Stats Computation"]
        COMPUTE --> RECENT[Query view_events<br/>last 7 days]
        COMPUTE --> DAILY[Query post_stats_daily<br/>days 8-30]
        
        RECENT --> COMBINE[Combine data sources]
        DAILY --> COMBINE
        
        COMBINE --> CALC_ALL[Calculate "all" stats]
        COMBINE --> CALC_AUTH[Calculate "authenticated" stats]
        
        CALC_ALL --> BUILD[Build PostStats object]
        CALC_AUTH --> BUILD
    end
    
    BUILD --> CACHE_SET[Cache in Redis<br/>TTL: 5 minutes]
    CACHE_SET --> RETURN
```

### Data Source Timeline

```mermaid
gantt
    title Statistics Data Sources
    dateFormat  YYYY-MM-DD
    axisFormat %d
    
    section Raw Events
    view_events (full detail)    :active, raw, 2024-12-19, 7d
    
    section Aggregates
    post_stats_daily (rolled up) :done, agg, 2024-11-26, 23d
    
    section Query Window
    30-day stats window          :crit, query, 2024-11-26, 30d
```

## Cache Invalidation

Stats cache is invalidated under these conditions:

```mermaid
flowchart LR
    subgraph Triggers
        VIEW[New view recorded]
        REACT[Reaction added/removed]
        COMMENT[Comment added/removed]
        ROLLUP[Daily rollup completed]
    end
    
    subgraph Cache
        REDIS[(Redis)]
        DB_CACHE[(post_stats_cache)]
    end
    
    VIEW --> |Not auto-invalidated| STALE[Cache becomes stale]
    REACT --> |Not auto-invalidated| STALE
    COMMENT --> |Not auto-invalidated| STALE
    
    STALE --> |TTL expires<br/>5 min| RECOMPUTE[Recompute on next request]
    
    ROLLUP --> |Hourly cleanup task| DB_CACHE
```

> **Note:** The current implementation relies on cache TTL expiration rather than explicit invalidation when views are recorded. This means stats may be up to 5 minutes stale.

## Error Handling

View tracking is designed to be **fail-safe** and **non-blocking**:

```mermaid
flowchart TD
    START[View capture attempt]
    
    START --> TRY{Try extract metadata}
    TRY -->|Exception| LOG1[Log warning, continue]
    TRY -->|Success| QUEUE{Try queue to Celery}
    
    QUEUE -->|Exception| LOG2[Log warning, continue]
    QUEUE -->|Success| RESPOND[Return response to user]
    
    LOG1 --> RESPOND
    LOG2 --> RESPOND
    
    subgraph "Celery Worker"
        TASK[write_view_event task]
        TASK --> DB{Write to DB}
        DB -->|Exception| RETRY[Retry with backoff<br/>max 3 attempts]
        DB -->|Success| DONE[Complete]
        RETRY -->|Exhausted| FAIL[Log error, discard]
    end
```

---

*See also: [Sources and Channels](./sources-and-channels.md) for details on view sources*

