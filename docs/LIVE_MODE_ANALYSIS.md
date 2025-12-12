# Live Mode Feature Analysis for p3a Firmware

**Version:** 1.0  
**Last Updated:** December 12, 2025  
**Status:** Planning & Analysis Phase

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Live Mode Requirements Overview](#live-mode-requirements-overview)
3. [Existing Infrastructure Analysis](#existing-infrastructure-analysis)
4. [Missing Components](#missing-components)
5. [Open Questions & Uncertainties](#open-questions--uncertainties)
6. [Edge Cases & Challenges](#edge-cases--challenges)
7. [Proposed Solutions](#proposed-solutions)
8. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

This document analyzes the requirements for implementing "Live Mode" in the p3a pixel art player firmware. Live Mode enables multiple p3a devices to display synchronized animations without direct device-to-device communication, relying instead on NTP time synchronization, deterministic random number generators, and shared master seeds.

**Key Finding:** The Makapix backend provides essential infrastructure (MQTT, post queries, player management), but **no p3a firmware code currently exists in this repository**. Live Mode implementation requires creating the entire p3a firmware from scratch, including all core playback, networking, and synchronization logic.

---

## Live Mode Requirements Overview

### Core Concept

Live Mode allows two or more p3a devices to:
- Display the **same animations** at the **same time**
- Show the **same frames** of those animations
- Achieve synchronization **without communicating with each other**
- Only sync with devices sharing the **same master seed** (default: 0xFAB)

### Live Mode Conditions

All the following must be true for devices to synchronize:
1. **Same content source:** Same channel OR same playlist
2. **Same wall clock time:** NTP-synchronized clocks
3. **Same play order:** Server order, created_at order, or reversible random order
4. **Same master seed:** Defaults to 0xFAB, configurable only on reboot
5. **No availability holes:** All needed animations are locally available in the play queue

### Key Mechanisms

#### 1. Seed Management
- **Boot time:** Generate true random seed via ESP32-P4 RNG
- **Effective seed (pre-NTP):** `true_random_seed XOR master_seed` → Out-of-sync, changes on every boot
- **Effective seed (post-NTP):** Just `master_seed` (0xFAB) → In-sync with other devices

#### 2. Swap Futures
- **swap_future:** A scheduled animation swap at a specific wall clock time
- **start-time:** Target wall clock time for the swap
- **start-frame:** Computed frame offset based on time elapsed since start-time
- **Usage:** 
  - On entering Live Mode: Jump to correct animation and frame
  - During Live Mode: Every automatic swap is a swap_future to readjust sync

#### 3. Time Abstraction
- **Channels:** Pretend channel started playing on its creation date (Jan 16, 2026 for all channels)
- **Playlists:** Pretend playlist started playing on its post creation date
- **Loop behavior:** Never stopped looping since creation
- **Purpose:** Given current wall clock time, deterministically compute which animation/frame should be playing

#### 4. User Interaction
- **Automated swaps:** Triggered by dwell time expiration, keep device in Live Mode
- **Manual swaps:** User-initiated `swap_next` or `swap_back` exit Live Mode

---

## Existing Infrastructure Analysis

### ✅ What EXISTS in the Makapix Backend

#### 1. MQTT Infrastructure (`/api/app/mqtt/`)
- **Player provisioning:** Device registration with 6-character codes
- **Command/status topics:** `makapix/player/{player_key}/command` and `/status`
- **Player authentication:** UUID-based player keys with owner mapping
- **Request/response pattern:** Bidirectional MQTT API for players

**Relevance to Live Mode:** Infrastructure for sending commands to devices exists, but current commands (`swap_next`, `swap_back`, `show_artwork`) are **manual control only**. No Live Mode coordination.

#### 2. Post Query System (`/api/app/mqtt/player_requests.py`)
- **Channel support:** "all", "promoted", "user", "by_user"
- **Sort orders:** "server_order", "created_at", "random"
- **Random seed support:** Reproducible random ordering via `random_seed` parameter
- **Pagination:** Cursor-based pagination for large result sets

**Relevance to Live Mode:** Players can query posts in deterministic order. Essential for Live Mode but needs firmware-side logic.

#### 3. Post Metadata (`/api/app/models.py`)
- **Animation data:** `frame_count`, `min_frame_duration_ms`
- **Timestamps:** `created_at` for deterministic time-based synchronization
- **Content data:** `art_url`, `width`, `height`, `has_transparency`

**Relevance to Live Mode:** Metadata needed to compute frame timings exists, but **no dwell time field**. Must use defaults or compute from metadata.

#### 4. Player Model
- **Owner relationship:** Each player belongs to a user
- **Status tracking:** Online/offline status, current_post_id
- **Device metadata:** `device_model`, `firmware_version`

**Relevance to Live Mode:** Player tracking exists but **no master seed storage**, **no Live Mode state tracking**.

### ❌ What DOES NOT EXIST

#### 1. p3a Firmware
- **No ESP32-P4 code:** Repository contains **zero** firmware files
- **No player logic:** No animation playback, frame rendering, timing control
- **No networking stack:** No Wi-Fi, NTP, MQTT client implementation

**Impact:** **Everything must be built from scratch**.

#### 2. Live Mode Backend Support
- **No master seed API:** No endpoint to store/retrieve player master seeds
- **No channel metadata:** Channel creation dates not tracked
- **No sync coordination:** Backend doesn't track or facilitate Live Mode state
- **No dwell time:** Posts don't have a `dwell_time_ms` field

**Impact:** Backend needs **minimal additions**.

#### 3. Time Synchronization
- **No NTP tracking:** Backend doesn't know if players are NTP-synced
- **No time-based commands:** MQTT commands have timestamps but no scheduled execution

**Impact:** NTP sync is **firmware responsibility**.

#### 4. Reversible Random Number Generator
- **No RRNG implementation:** No algorithm for deterministic random walks

**Impact:** RRNG must be **implemented in firmware**.

---

## Missing Components

### Backend (Minimal Changes Needed)

#### 1. Master Seed Storage
```sql
ALTER TABLE players 
ADD COLUMN master_seed INTEGER NOT NULL DEFAULT 4011;  -- 0xFAB in hex = 4011 in decimal
```

#### 2. Channel Metadata
Options:
- Hardcode channel creation date as Jan 16, 2026
- Add `channels` table with `name` and `created_at`

#### 3. Dwell Time Specification
Options:
1. Add `dwell_time_ms` to posts table (explicit per-post)
2. Compute from animation metadata
3. Use global defaults: 5000ms for static, computed for animated
4. Layered defaults: User > playlist > post > global

**Recommendation:** Start with option 3.

#### 4. NTP Sync Status Reporting
```python
{
  "player_key": "...",
  "status": "online",
  "ntp_synced": true,  # NEW
  ...
}
```

### Firmware (Complete Implementation Needed)

#### 1. Core Player Engine
- Image decoder (PNG, GIF, WebP)
- Frame buffer management
- Display output to LED matrix
- Animation timing

**Estimated effort:** 2-4 weeks

#### 2. Networking Stack
- Wi-Fi connection management
- TLS support for MQTT
- HTTP client for downloads
- NTP client for time sync

**Estimated effort:** 1-2 weeks (ESP-IDF provides most)

#### 3. MQTT Integration
- Provision flow
- Command/status protocol
- Subscribe/publish

**Estimated effort:** 1 week

#### 4. Content Management
- Query posts via MQTT
- Download images
- Local cache management

**Estimated effort:** 1-2 weeks

#### 5. Seed Management & RRNG
- True RNG on boot
- Master seed XOR logic
- Reversible Random Number Generator

**Estimated effort:** 3-5 days

#### 6. NTP Client
- NTP query and RTC sync
- Track sync status
- Periodic re-sync

**Estimated effort:** 2-3 days (ESP-IDF has SNTP)

#### 7. Live Mode Logic
- Enter/exit Live Mode
- Virtual start time calculation
- Current position computation
- swap_future scheduling
- Clock drift compensation

**Estimated effort:** 2-3 weeks

#### 8. Configuration & State Management
- NVS storage for master seed
- RAM state for Live Mode
- Config API integration

**Estimated effort:** 3-5 days

---

## Open Questions & Uncertainties

### 1. Channel Creation Date
**Question:** What is the actual channel creation date?

**Issue:** Requirement states "all channels were created on Jan. 16, 2026" which is approximately one month in the future from the time of this writing (Dec 2025).

**Decision needed:** Clarify if this is the intended date or if it should be Jan 16, 2025 (past), and confirm timezone (UTC assumed).

### 2. Dwell Time Defaults
**Question:** What are the default dwell times?

**Unknowns:**
- Default for static images (3s? 5s? 10s?)
- Default for animated GIFs (loop once? fixed duration?)
- Customization hierarchy

**Decision needed:** Define dwell time defaults and hierarchy.

### 3. RRNG Algorithm
**Question:** Which reversible RNG to use?

**Options:**
1. Linear Congruential Generator (LCG) - fast, proven
2. XORshift - fast, good distribution
3. Hash-based (SHA256) - simple, perfectly reversible

**Recommendation:** Hash-based for simplicity:
```c
uint32_t rrng(uint32_t seed, uint32_t index) {
    uint8_t input[8];
    memcpy(input, &seed, 4);
    memcpy(input + 4, &index, 4);
    uint8_t hash[32];
    sha256(input, 8, hash);
    return *(uint32_t*)hash;
}
```

### 4. Frame-Level Synchronization Accuracy
**Question:** How accurate does frame sync need to be?

**Acceptable drift:**
- ±100ms? → Visually noticeable
- ±50ms? → Might be acceptable
- ±16ms (1 frame @ 60fps)? → Very tight

**Decision needed:** Define tolerance.

### 5. Play Queue Availability Holes
**Question:** How to handle missing posts?

**Options:**
1. Strict mode: Only sync if identical post sets
2. Skip mode: Skip unavailable (but desync)
3. Wait mode: Fetch missing content
4. Fallback mode: Exit Live Mode

**Recommendation:** Option 4 initially, option 3 later.

### 6. Playlist vs. Channel Priority
**Question:** Which creation date for playlists containing channel posts?

**Recommendation:** Use playlist creation date. Independent sync contexts.

### 7. Animation Loop Behavior
**Question:** How to calculate dwell time for animated GIFs?

**Recommendation:** Use `frame_count * min_frame_duration_ms` from metadata.

### 8. Time Zone Handling
**Recommendation:** **Always UTC** for all time calculations.

### 9. Master Seed Change Timing
**Requirement:** "can only be changed on reboot"

**Clarification needed:** Can it be set via web UI for next reboot?

### 10. Entering/Exiting Live Mode
**Question:** Manual toggle or auto-detect?

**Recommendation:** Auto-detect (simpler UX).

---

## Edge Cases & Challenges

### 1. Clock Drift
**Solution:**
- Re-sync NTP hourly
- Recalculate offset on each swap_future
- Accept ±50ms tolerance

### 2. Network Interruptions
**Solution:**
- Continue with cached content
- Exit Live Mode if can't fetch next post
- Re-enter after reconnection

### 3. Partial Post Availability
**Solutions:**
- Prefetch upcoming posts aggressively
- Check availability before entering Live Mode
- Exit if unavailable post is next

### 4. Mid-Animation Entry
**Solution:**
```
total_ms = frame_count * min_frame_duration_ms
time_into_animation = (now - start) % total_ms
start_frame = floor(time_into_animation / frame_duration)
```

### 5. Empty Channels/Playlists
**Solution:**
- Check post count before entering
- Display "No content" message

### 6. Conflicting Play Orders
**Solution:** Play order is part of Live Mode conditions.

### 7. Extremely Fast Animations
**Solution:** Accept lower precision for very fast animations.

### 8. Playlist Edits During Playback
**Solution:**
- Use playlist version/timestamp
- Exit Live Mode if modified

### 9. Post Deletion
**Solution:**
- Skip deleted posts (404 from API)
- All devices skip together

### 10. Master Seed Mismatch
**Solution:**
- Display master seed in UI
- Web UI shows sync groups

### 11. Timezone Weirdness
**Solution:** Always use UTC internally.

### 12. First Boot (No NTP Yet)
**Expected:** Play out-of-sync with random seed (by design).

### 13. Backend Downtime
**Solution:** Play cached content, retry periodically.

### 14. Rapid Manual Swaps
**Solution:** Exit Live Mode, could auto re-enter after 60s.

### 15. Dwell Time Overrides
**Clarification needed:** Are custom dwell times compatible with Live Mode?

---

## Proposed Solutions

### Solution 1: Backend Enhancements (Minimal)

#### 1.1 Database Schema
```sql
ALTER TABLE players 
ADD COLUMN master_seed INTEGER NOT NULL DEFAULT 4011;  -- 0xFAB in hex

ALTER TABLE posts 
ADD COLUMN dwell_time_ms INTEGER NULL;

CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT '2026-01-16 00:00:00+00'
);
```

#### 1.2 API Endpoints
```python
# GET /api/player/config
@router.get("/player/config")
async def get_player_config(player: Player = Depends(get_current_player)):
    return {
        "master_seed": player.master_seed,
        "channel_metadata": {
            "all": {"created_at": "2026-01-16T00:00:00Z"},
            "promoted": {"created_at": "2026-01-16T00:00:00Z"}
        }
    }
```

#### 1.3 Status Message Enhancement
```python
class PlayerStatus(BaseModel):
    ntp_synced: bool  # NEW
    live_mode_active: bool  # NEW
    ...
```

### Solution 2: Firmware Architecture

```
p3a_firmware/
├── main/
│   ├── network/
│   │   ├── wifi_manager.c
│   │   ├── ntp_client.c
│   │   ├── mqtt_client.c
│   │   └── http_client.c
│   ├── player/
│   │   ├── player_core.c
│   │   ├── animation_loader.c
│   │   └── display_driver.c
│   ├── sync/
│   │   ├── live_mode.c
│   │   ├── seed_manager.c
│   │   └── rrng.c
│   └── utils/
│       ├── nvs_storage.c
│       └── time_utils.c
└── platformio.ini
```

### Solution 3: Reversible RNG

Hash-based RRNG using SHA-256:
```c
uint32_t rrng(uint32_t seed, uint32_t index) {
    uint8_t input[8];
    memcpy(input, &seed, 4);
    memcpy(input + 4, &index, 4);
    uint8_t hash[32];
    mbedtls_sha256(input, 8, hash, 0);
    uint32_t result;
    memcpy(&result, hash, 4);
    return result;
}
```

### Solution 4: Dwell Time Strategy

```c
int64_t get_dwell_time(Post* post, Playlist* playlist) {
    if (playlist && playlist->default_dwell_ms > 0) {
        return playlist->default_dwell_ms;
    }
    if (post->dwell_time_ms > 0) {
        return post->dwell_time_ms;
    }
    if (post->frame_count > 1 && post->min_frame_duration_ms > 0) {
        return post->frame_count * post->min_frame_duration_ms;
    }
    return 5000;  // 5 seconds default
}
```

### Solution 5: Channel Creation Date

Hardcode in firmware:
```c
#define CHANNEL_CREATION_TIME_MS 1768521600000LL  // 2026-01-16 00:00:00 UTC
```

---

## Implementation Roadmap

### Phase 0: Repository Setup (Week 1)
- [ ] Create `firmware/p3a/` directory
- [ ] Set up PlatformIO for ESP32-P4
- [ ] Configure build system
- [ ] Add ESP-IDF framework

### Phase 1: Core Backend Support (Week 1-2)
- [ ] Add `master_seed` column to players table
- [ ] Implement `GET /api/player/config`
- [ ] Implement `POST /api/player/config`
- [ ] Add `ntp_synced` to status schema
- [ ] Add channel creation constants
- [ ] Add `dwell_time_ms` to posts (nullable)

**Deliverable:** Backend supports Live Mode.

### Phase 2: Firmware Foundation (Week 2-4)
- [ ] Wi-Fi manager
- [ ] NTP client
- [ ] MQTT client
- [ ] Provisioning flow
- [ ] Command/status protocol
- [ ] HTTP client

**Deliverable:** p3a connects to backend.

### Phase 3: Content Management (Week 4-6)
- [ ] MQTT request/response client
- [ ] query_posts handler
- [ ] Image downloader
- [ ] Local cache
- [ ] Cache management

**Deliverable:** p3a queries and caches artwork.

### Phase 4: Basic Playback (Week 6-8)
- [ ] Image decoder (PNG, GIF, WebP)
- [ ] Frame buffer
- [ ] LED matrix driver
- [ ] Animation playback
- [ ] Manual swap commands

**Deliverable:** p3a displays artwork.

### Phase 5: Seed Management & RRNG (Week 8-9)
- [ ] True RNG
- [ ] NVS storage
- [ ] Seed XOR logic
- [ ] Hash-based RRNG
- [ ] Fisher-Yates shuffle
- [ ] Fetch master seed from backend

**Deliverable:** Reproducible random playback.

### Phase 6: Live Mode Core (Week 9-11)
- [ ] Live Mode state machine
- [ ] enter_live_mode() logic
- [ ] Virtual start time calculation
- [ ] Dwell time computation
- [ ] Current position calculation
- [ ] swap_future scheduling
- [ ] Automatic swap with sync
- [ ] Manual swap → exit

**Deliverable:** Basic Live Mode working.

### Phase 7: Live Mode Refinement (Week 11-13)
- [ ] Mid-animation entry
- [ ] Playlist-based sync
- [ ] Availability checking
- [ ] Graceful degradation
- [ ] Periodic NTP re-sync
- [ ] Clock drift compensation
- [ ] Status indicators

**Deliverable:** Robust Live Mode.

### Phase 8: Polish & Testing (Week 13-14)
- [ ] Config UI
- [ ] Logging and diagnostics
- [ ] OTA update support
- [ ] Performance optimization
- [ ] Multi-device testing
- [ ] Stress testing
- [ ] Documentation

**Deliverable:** Production-ready firmware.

### Phase 9: Advanced Features (Week 14+)
- [ ] GIF variable frame durations
- [ ] WebP animation
- [ ] Custom dwell times
- [ ] Sync group visualization
- [ ] Advanced diagnostics

**Deliverable:** Enhanced Live Mode.

---

## Summary & Next Steps

### Key Findings

1. **Backend is mostly ready:** MQTT, player management, and post queries exist. Need master seed storage and minor enhancements.

2. **Firmware doesn't exist:** Entire p3a firmware must be built from scratch (~14 weeks).

3. **Core complexity is Live Mode logic:** Synchronization algorithm, mid-animation entry, clock drift compensation.

4. **Several design decisions needed:** Dwell times, RRNG, sync accuracy, etc.

### Recommended Immediate Actions

1. **Clarify requirements:**
   - Channel creation date
   - Dwell time defaults
   - Sync accuracy tolerance
   - Dwell time customization compatibility

2. **Prioritize backend work:**
   - Add master_seed to players
   - Implement config endpoints
   - Update status schema

3. **Begin firmware prototyping:**
   - Set up ESP32-P4 environment
   - Test display hardware
   - Test NTP sync accuracy

4. **Create test plan:**
   - Define sync accuracy methodology
   - Build measurement tools
   - Document expected behavior

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Firmware complexity | 4-6 months instead of 3 | Start with MVP, iterate |
| NTP accuracy insufficient | Can't achieve frame sync | Relax accuracy to ±100ms |
| Hardware limitations | Can't decode/render fast | Pre-decode, optimize |
| Channel metadata missing | Can't compute start times | Hardcode dates initially |
| RRNG not reversible | Devices differ | Use proven SHA-256 |

### Success Criteria

- ✅ Two p3a devices sync within ±100ms
- ✅ Devices sync across reboots
- ✅ Manual swap exits Live Mode
- ✅ NTP sync loss handled
- ✅ Random playback deterministic

---

**Document Status:** Ready for review

**Authors:** GitHub Copilot  
**Reviewers:** [TBD]  
**Approval:** [TBD]
