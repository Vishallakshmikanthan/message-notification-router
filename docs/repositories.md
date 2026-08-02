# Repository Pattern & Data Access Layer Specification

## 1. Overview & Architectural Principles

The **Repository Pattern** encapsulates data storage mechanisms and provides clean, object-oriented domain access interfaces. It decouples business logic and lookup services from physical dataset persistence representations.

### Key Architectural Rules
1. **Data Ownership**: Each repository strictly owns its domain data structure. Direct modification of internal repository collections by external components is strictly prohibited.
2. **Immutability & Read-Only Exposure**: Repositories expose immutable collections or read-only domain objects to prevent accidental state corruption.
3. **Thread Safety**: All read operations are thread-safe and lock-free under standard runtime conditions.
4. **Primary Key O(1) Access Guarantee**: Repositories must maintain primary hash indexes guaranteeing O(1) constant-time entity retrieval.

---

## 2. Base Repository Interface Contract

All concrete repositories adhere to the standard `IRepository<TEntity, TKey>` contract:

- **`GetById(TKey key) -> TEntity?`**: Performs an O(1) primary index lookup. Returns `Entity` or `Null`.
- **`GetAll() -> ReadOnlyCollection<TEntity>`**: Returns an immutable collection of all entities.
- **`Exists(TKey key) -> Boolean`**: Evaluates primary index key presence in O(1) time.
- **`Count() -> Integer`**: Returns the total number of managed records.

---

## 3. Concrete Repository Specifications

---

### 3.1 `MessageRepository`

#### Purpose & Responsibilities
Manages incoming primary message evaluation instances originating from `messages.csv`. Serves as the primary message stream repository evaluated by context builders and routing logic.

#### Data Ownership
- **Primary Source**: `messages.csv`
- **Owned Entities**: `Message` objects.
- **Lifecycle**: Initialized during Stage 7 of system boot. Read-heavy during routing evaluation.

#### Underlying Data Structures & Indexing
- **Primary Collection**: Array / List of `Message` entities maintaining incoming stream sequence.
- **Primary Index**: `Map<String, Message>` indexed by `message_id`.
- **Secondary Index**: `Map<String, List<Message>>` indexed by `user_id` (Recipient).
- **Secondary Index**: `Map<String, List<Message>>` indexed by `conversation_type`.

#### Performance Considerations
- Iteration memory overhead minimized via pre-allocated list capacity matching batch size.
- Fast streaming cursor access pattern supported for sequential evaluation.

---

### 3.2 `UserRepository`

#### Purpose & Responsibilities
Stores recipient user profiles (`users.csv`) including 30-day interaction activity, quiet hours (`do_not_disturb_window`), open counts, reply counts, dismissal counts, and spam report history.

#### Data Ownership
- **Primary Source**: `users.csv`
- **Owned Entities**: `User` objects.
- **Lifecycle**: Loaded during Stage 2. Immutable during runtime execution.

#### Underlying Data Structures & Indexing
- **Primary Index**: `Map<String, User>` indexed by `user_id` (`u_001` - `u_055`).

#### Performance & Caching
- 100% in-memory resident (55 records, ~5 KB RAM footprint).
- Zero cache invalidation; immutable lifetime.

---

### 3.3 `GroupRepository`

#### Purpose & Responsibilities
Manages WhatsApp group metadata (`groups.csv`) and group membership/user settings (`group_members.csv`). Computes and stores admin roles, joining dates, user group activity stats, and explicit group mute states.

#### Data Ownership
- **Primary Sources**: `groups.csv`, `group_members.csv`
- **Owned Entities**: `Group` metadata entities, `GroupMember` junction entities.
- **Lifecycle**: Loaded during Stage 2 (groups) and Stage 3 (group members).

#### Underlying Data Structures & Indexing
- **Primary Index**: `Map<String, Group>` indexed by `group_id`.
- **Junction Primary Index**: `Map<Tuple<String, String>, GroupMember>` indexed by composite key `(group_id, user_id)`.
- **Secondary Relationship Index**: `Map<String, List<GroupMember>>` indexed by `group_id` (group roster).
- **Secondary Relationship Index**: `Map<String, List<String>>` indexed by `user_id` (groups joined per user).
- **Admin Fast Index**: `Set<Tuple<String, String>>` containing `(group_id, user_id)` tuples for instant admin rights verification.

#### Performance Considerations
- Direct O(1) resolution of user membership, admin privileges, and group-mute settings via composite hash map lookup.

---

### 3.4 `BusinessRepository`

#### Purpose & Responsibilities
Stores verified business sender profiles (`business_accounts.csv`) and user-business interaction histories (`user_business_history.csv`). Tracks brand verification status, category, domain integrity parameters, promotional opt-out states, and 180-day interaction activity counts.

#### Data Ownership
- **Primary Sources**: `business_accounts.csv`, `user_business_history.csv`
- **Owned Entities**: `BusinessAccount` profiles, `UserBusinessHistory` entities.
- **Lifecycle**: Loaded during Stage 2 and Stage 3.

#### Underlying Data Structures & Indexing
- **Primary Index**: `Map<String, BusinessAccount>` indexed by `business_id`.
- **Junction Primary Index**: `Map<Tuple<String, String>, UserBusinessHistory>` indexed by composite key `(user_id, business_id)`.
- **Domain Lookup Index**: `Map<String, List<BusinessAccount>>` indexed by `official_domain`.

#### Performance Considerations
- Domain mismatch logic (`official_domain` vs `domain_used_by_sender`) pre-calculated during loading to prevent string comparison overhead during context resolution.

---

### 3.5 `MediaRepository`

#### Purpose & Responsibilities
Manages media pointer metadata (`images.csv`, `voice_notes.csv`) and verifies physical disk existence paths managed by `FileManager`.

#### Data Ownership
- **Primary Sources**: `images.csv`, `voice_notes.csv`, physical disk paths (`dataset/media/`).
- **Owned Entities**: `ImageManifest`, `VoiceNoteManifest` records.
- **Lifecycle**: Loaded during Stage 4 following Stage 1 file system audit.

#### Underlying Data Structures & Indexing
- **Image Primary Index**: `Map<String, ImageManifest>` indexed by `image_id`.
- **Audio Primary Index**: `Map<String, VoiceNoteManifest>` indexed by `voice_note_id`.
- **Disk Verification Set**: `Set<String>` of validated physical disk path pointers.

#### Performance Considerations
- Guarantees instant O(1) detection of orphaned media pointers or missing media files.

---

### 3.6 `HistoryRepository`

#### Purpose & Responsibilities
Stores historical message records (`message_history.csv`) representing past interaction trajectories between users, groups, and business accounts.

#### Data Ownership
- **Primary Source**: `message_history.csv`
- **Owned Entities**: `HistoricalMessage` entities.
- **Lifecycle**: Loaded during Stage 5.

#### Underlying Data Structures & Indexing
- **Primary Index**: `Map<String, HistoricalMessage>` indexed by `message_id`.
- **User Trajectory Index**: `Map<String, List<HistoricalMessage>>` indexed by `user_id` (Sorted by `created_at`).
- **User-Sender Trajectory Index**: `Map<Tuple<String, String>, List<HistoricalMessage>>` indexed by `(user_id, sender_id)`.
- **User-Business Trajectory Index**: `Map<Tuple<String, String>, List<HistoricalMessage>>` indexed by `(user_id, business_id)`.

#### Performance Considerations
- Lists are pre-sorted chronologically at boot time, enabling fast sliding-window trajectory slicing without runtime sorting overhead.

---

### 3.7 `EventRepository`

#### Purpose & Responsibilities
Tracks message event logs (`message_events.csv`) recording delivery, read receipt, reply, and dismissal events associated with historical messages.

#### Data Ownership
- **Primary Source**: `message_events.csv`
- **Owned Entities**: `MessageEvent` entities.
- **Lifecycle**: Loaded during Stage 5.

#### Underlying Data Structures & Indexing
- **Primary Composite Index**: `Map<Tuple<String, String>, MessageEvent>` indexed by `(user_id, message_id)`.
- **Secondary Index**: `Map<String, List<MessageEvent>>` indexed by `user_id`.

---

### 3.8 `NotificationSummaryRepository`

#### Purpose & Responsibilities
Manages aggregated daily notification time-series summaries (`daily_notification_summary.csv`) detailing daily incoming volume, open rates, and dismissal frequencies per user.

#### Data Ownership
- **Primary Source**: `daily_notification_summary.csv`
- **Owned Entities**: `DailyNotificationSummary` entities.
- **Lifecycle**: Loaded during Stage 6.

#### Underlying Data Structures & Indexing
- **Primary Composite Index**: `Map<Tuple<String, String>, DailyNotificationSummary>` indexed by `(user_id, date)`.
- **User Summary Trajectory**: `Map<String, List<DailyNotificationSummary>>` indexed by `user_id` (Sorted by `date`).

#### Performance Considerations
- Enables instantaneous O(1) computation of baseline user daily notification statistics.
