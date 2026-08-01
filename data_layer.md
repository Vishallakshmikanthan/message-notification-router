# Data Layer Architecture & Subsystem Specification

## 1. Executive Summary & System Scope

The **Data Layer** serves as the single, authoritative, language-agnostic data access foundation for the AI-powered WhatsApp Message Notification Router. Designed according to **Clean Architecture** and **SOLID** principles, this layer completely decouples underlying file storage representations (13 CSV datasets and physical media folders) from downstream processing engines. 

Every future system component—including Signal Generators, Decision Engines, Routing Controllers, and Action Handlers—is strictly prohibited from interacting with CSV files directly. All data access must pass through the Data Layer's contracts, ensuring high-throughput O(1) in-memory lookups, strict referential integrity, zero data duplication, and a deterministic execution lifecycle.

---

## 2. Data Loading Architecture (`DataLoader`)

### 2.1 Overview & Design Goals
The `DataLoader` executes a deterministic, multi-stage ingestion pipeline during system boot. It guarantees that base entities, relationship maps, media pointer manifests, historical logs, and metrics are ingested and validated in strict topological order before accepting incoming inference streams.

```
+-----------------------------------------------------------------------------------+
|                            7-STAGE DETERMINISTIC PIPELINE                         |
+-----------------------------------------------------------------------------------+
| Stage 1: Physical Media File System Audit (images/, audio/)                      |
| Stage 2: Static Base Entity Loading (users.csv, groups.csv, business_accounts.csv)|
| Stage 3: Junction & Relationship Loading (group_members.csv, user_business.csv)  |
| Stage 4: Media Manifest Resolution (images.csv, voice_notes.csv)                  |
| Stage 5: Historical Corpus & Events (message_history.csv, message_events.csv)     |
| Stage 6: Aggregated Time-Series Summaries (daily_notification_summary.csv)        |
| Stage 7: Primary Incoming Stream Processing (messages.csv)                       |
+-----------------------------------------------------------------------------------+
```

### 2.2 Stage-by-Stage Processing Pipeline

#### Stage 1: Physical Media Audit
- **Input**: Absolute file system path pointers to `dataset/media/images/` and `dataset/media/audio/`.
- **Operations**:
  - Scans physical storage directories.
  - Generates an in-memory `HashSet<String>` containing verified relative disk paths.
- **Output**: Physical media existence index (`MediaDiskIndex`).

#### Stage 2: Static Base Entity Ingestion
- **Input**: `users.csv`, `groups.csv`, `business_accounts.csv`.
- **Operations**:
  - Ingests raw rows via abstract stream reader.
  - Applies Level 1 (Structural) and Level 2 (Type Coercion) validations.
  - Instantiates immutable domain entities (`User`, `Group`, `BusinessAccount`).
  - Populates primary entity hash tables (`UserRepository`, `GroupRepository`, `BusinessRepository`).
- **Output**: Base entity repositories indexed by primary keys (`user_id`, `group_id`, `business_id`).

#### Stage 3: Junction & Relationship Ingestion
- **Input**: `group_members.csv`, `user_business_history.csv`.
- **Operations**:
  - Validates Level 3 Foreign Key integrity against Stage 2 Base Entity Repositories.
  - Constructs composite-key lookup maps: `(group_id, user_id)` and `(user_id, business_id)`.
  - Builds inverted relationship indexes (e.g., list of groups per user, user admin rights).
- **Output**: Population of membership and interaction relationship indexes.

#### Stage 4: Media Manifest Resolution
- **Input**: `images.csv`, `voice_notes.csv`.
- **Operations**:
  - Validates manifest pointers (`image_id`, `voice_note_id`).
  - Cross-references manifest `file_path` entries against the `MediaDiskIndex` constructed in Stage 1.
  - Flags missing or unreadable physical files.
- **Output**: `MediaRepository` with guaranteed physical disk resolution pointers.

#### Stage 5: Historical Message Corpus & Event Logs
- **Input**: `message_history.csv`, `message_events.csv`.
- **Operations**:
  - Ingests historical message logs and associated status delivery events.
  - Validates FK mappings to `users.user_id` and `business_accounts.business_id`.
  - Constructs historical trajectory timelines sorted chronologically by `created_at`.
- **Output**: `HistoryRepository` and `EventRepository` with index maps by `user_id` and `(user_id, message_id)`.

#### Stage 6: Aggregated Time-Series Ingestion
- **Input**: `daily_notification_summary.csv`.
- **Operations**:
  - Validates daily notification metrics (`messages_received`, `notifications_opened`, `notifications_dismissed`).
  - Constructs composite index map `(user_id, date)`.
- **Output**: `NotificationSummaryRepository`.

#### Stage 7: Primary Incoming Stream Resolution
- **Input**: `messages.csv` (Primary evaluation dataset).
- **Operations**:
  - Pre-validates incoming candidate messages for routing context evaluation.
  - Prepares message queues for batch or streaming consumption by downstream context builders.

---

## 3. Data Manager (`DataManager`)

### 3.1 Role & Architecture
`DataManager` is the facade and entry point for the entire Data Layer. It encapsulates all sub-components (Bootstrapper, Repositories, Indexes, Cache, Lookup Services, Context Builder, File/Resource Managers) and exposes a clean management API to the runtime environment.

### 3.2 Key Management Lifecycle
1. **`Initialize()`**: Triggers `DataLoader` and executes the 7-stage boot sequence.
2. **`GetStatus()`**: Returns real-time health, memory usage, and repository record counts.
3. **`Reload()`**: Performs an atomic in-memory hot-reload of underlying data structures.
4. **`Shutdown()`**: Safely flushes caches, closes file handles, and frees allocated memory.

---

## 4. File Manager (`FileManager`)

### 4.1 Overview & Responsibilities
`FileManager` isolates physical file system interactions from memory-resident data repositories. It manages path resolution, disk accessibility auditing, and binary stream reading for audio and image assets.

### 4.2 Core Operating Rules
- Maintains a thread-safe disk registry of valid media paths.
- Provides fast O(1) file availability checks without incurring synchronous blocking I/O latency during message context building.
- Normalizes Windows and UNIX file path representations (`\` vs `/`).

---

## 5. Resource Manager (`ResourceManager`)

### 5.1 RAM Footprint Control (<5 MB Limit)
The total dataset size across all 13 CSV files is approximately 1.2 MB. `ResourceManager` enforces strict memory allocation constraints to guarantee that the total in-memory representation never exceeds **5.0 MB RAM**.

### 5.2 Thread Safety & Concurrency Control
- **Read Heavy Optimizations**: Uses lock-free read semantics (copy-on-write or atomic reference pointers) for fast concurrent queries.
- **Write/Reload Locks**: Implements reader-writer lock primitives (`ReadWriteLock`) during system state transitions or re-indexing operations.

---

## 6. Memory Management Strategy

### 6.1 Zero-Copy Reference Sharing
Entities stored in repositories are immutable data objects. Lookup services and `MessageContext` objects hold direct, read-only references to repository entities rather than creating deep copies, keeping memory consumption near zero during context construction.

### 6.2 String Interning Pool
To eliminate duplicate string allocation in RAM:
- High-cardinality categorical strings (e.g., `conversation_type`, `group_type`, `category`, `media_type`, `role`) and repeated string identifiers (e.g., `user_id`, `group_id`, `business_id`) are routed through a central **String Interning Pool**.
- Saves ~40% of standard heap overhead.

### 6.3 Fixed-Slot Struct Layouts
Domain objects utilize compact, fixed-attribute slot representations, avoiding dynamic dictionary key-overhead.

---

## 7. Lazy Loading Strategy

### 7.1 Virtualized Media Asset Audit
- Physical media metadata pointers are indexed at boot time, but heavy binary file contents (raw image bytes / audio buffers) are **never** loaded into memory during Data Layer initialization.
- File system reads are deferred until explicitly requested by downstream specialized media handlers.

### 7.2 Deferred Historical Trajectory Deep Scans
- Summary statistics (30-day / 180-day metrics) are pre-calculated and indexed during boot.
- Detailed historical message trajectories are loaded into active context lazily only when specific context builder rules demand full message text histories.

---

## 8. Error Recovery Strategy

### 8.1 Degraded Operational Mode
If a non-critical CSV dataset fails validation (e.g., optional historical summaries corrupted or missing), `DataManager` enters **Degraded Mode**:
- Logs severity warning alerts to the telemetry subsystem.
- Serves default fallback metric objects (`DefaultUserSummary`, `DefaultInteractionHistory`).
- Prevents total system crashes caused by minor non-critical data flaws.

### 8.2 Safe Null Coalescing & Missing FK Fallbacks
When a foreign key reference cannot be resolved (e.g., a message sent by an unindexed user ID):
- The `SchemaValidator` isolates the row into a **Quarantine Log**.
- The `ContextBuilder` substitutes a pre-initialized `SystemFallbackProfile` entity to maintain structural context safety.

---

## 9. Logging & Telemetry Strategy

### 9.1 Structured JSON Telemetry
All Data Layer events emit structured JSON log entries containing:
- Timestamp (UTC ISO 8601)
- Log Level (`TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL`)
- Component Name (`DataLoader`, `SchemaValidator`, `CacheManager`)
- Telemetry Context (Execution stage, row count, execution time in milliseconds, memory delta)

### 9.2 Audit Log Categories
1. **Boot Audit Log**: Tracks ingestion duration, entity counts, and validation status per CSV stage.
2. **Schema Violation Log**: Details specific row failures, invalid values, and referential integrity breaches.
3. **Cache Telemetry Log**: Monitors cache hit/miss ratios, eviction counts, and memory footprint metrics.
