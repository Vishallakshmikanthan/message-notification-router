# Multi-Tiered Cache Architecture & CacheManager Specification

## 1. Overview & Architectural Role

The **Cache Subsystem** provides sub-millisecond query acceleration for high-frequency, computationally intensive, or composite domain lookups. Managed centrally by **`CacheManager`**, the caching framework ensures strict memory caps, explicit invalidation boundaries, and thread-safe concurrent access.

---

## 2. Categorized Caching Tiers

```
+-----------------------------------------------------------------------------------+
|                                 CACHE MANAGER                                     |
+-----------------------------------------------------------------------------------+
| Tier 1: Static Base Entity Cache    | Read-Only | Immutable | Zero Eviction       |
| Tier 2: Lookup & Relationship Cache | Read-Heavy| LRU (1000)| Dynamic Eviction    |
| Tier 3: History & Trajectory Cache  | Time-Bound| TTL (300s)| Time-based Eviction  |
| Tier 4: Media Disk Verification Cache| Bit-Set  | Immutable | Boot Verified       |
+-----------------------------------------------------------------------------------+
```

### 2.1 Tier 1: Static Base Entity Cache
- **Managed Entities**: `User`, `Group`, `BusinessAccount` base entities.
- **Eviction Strategy**: **NONE**. Permanently retained in memory during system operational lifecycle.
- **Rationale**: Total base entity count is small (55 users, 24 groups, 111 businesses; ~200 KB total RAM). Retaining these entities in memory eliminates hash map re-allocations and lookups.

### 2.2 Tier 2: Enriched Lookup & Relationship Cache
- **Managed Entries**: Pre-assembled `PersonalChannelContext`, `GroupChannelContext`, `BusinessChannelContext` objects.
- **Eviction Strategy**: **Least Recently Used (LRU)** with a capacity cap of 1,000 active context objects.
- **Rationale**: Prevents re-computing complex domain mismatch logic, admin rights checks, and mutual group intersections for repeated messages from the same sender or group.

### 2.3 Tier 3: History & Trajectory Cache
- **Managed Entries**: Aggregated interaction trajectory metrics (e.g. 30-day message exchange counts, user reply rates, daily baseline averages).
- **Eviction Strategy**: **Time-To-Live (TTL)** set to **300 seconds (5 minutes)**.
- **Rationale**: Trajectory metrics change slowly over time. TTL caching prevents costly list iterations over historical message logs.

### 2.4 Tier 4: Media Disk Verification Cache
- **Managed Entries**: Disk existence bit-masks and file handle pointer paths for image and audio media assets.
- **Eviction Strategy**: **NONE** (Immutable after Stage 1 boot audit).
- **Rationale**: Eliminates physical disk system calls (`stat`, `access`) during message context construction.

---

## 3. Cache Rules: Exclusions & Mandatory Caching

### 3.1 What MUST Be Cached
- Pre-parsed quiet hours evaluation ranges (`do_not_disturb_window`).
- Computed domain mismatch boolean flags (`official_domain != domain_used_by_sender`).
- Inverted group membership administrative privileges (`GroupAdminSet`).
- Mutual group count intersections between recipient and sender users.

### 3.2 What MUST NEVER Be Cached
- Raw incoming stream messages prior to schema validation.
- Unvalidated media file stream handles.
- Transient processing state variables or active error exception traces.
- Corrupted rows quarantined during loading stages.

---

## 4. Cache Invalidation & Management Lifecycle

### 4.1 Invalidation Trigger Hooks
1. **Event-Driven Invalidation**: If a stateful mutator updates a group membership record or business opt-out timestamp, `CacheManager.InvalidateKey(cacheTier, key)` immediately purges stale cached contexts.
2. **TTL Expiration**: Tier 3 history entries automatically expire after 300 seconds and are lazily evicted upon next access.
3. **Explicit System Reset**: `DataManager.Reload()` executes `CacheManager.PurgeAll()`, clearing all cache tiers prior to re-ingesting datasets.

### 4.2 Telemetry & Monitoring
`CacheManager` tracks real-time operational statistics exposed via `GetStats()`:
- Total Requests
- Cache Hits & Cache Misses
- Hit Ratio Percentage (`Hits / Total Requests * 100`)
- Current Memory Footprint (Bytes)
- Eviction Count per Tier
