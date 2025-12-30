# Sources and Channels

This document describes the various sources from which view events can originate and the channel/intent classification system.

> **⚠️ FEATURE POSTPONED: Blog Posts**
> 
> As of December 2025, blog post functionality has been postponed to an indeterminate future date.
> This document currently covers view tracking for artwork only. Blog post view tracking is implemented
> but not exposed to users until the feature is reactivated.

## View Sources

Views can originate from four distinct sources:

```mermaid
mindmap
  root((View Sources))
    Web
      Desktop browsers
      Mobile browsers
      Tablet browsers
    Player
      p3a devices
      Future players
    Widget
      Embedded on external sites
      GitHub Pages galleries
    API
      Third-party clients
      Custom integrations
```

### Source: Web

Views from the Makapix Club website, accessed through standard web browsers.

| Aspect | Details |
|--------|---------|
| **Protocol** | HTTPS |
| **Detection** | Default source for HTTP API requests |
| **Device types** | Desktop, mobile, tablet |
| **Auth** | Optional (supports anonymous) |
| **Metadata** | Full (IP, user agent, referer, country) |

### Source: Player

Views from physical Makapix player devices (p3a and others) connected via MQTT.

| Aspect | Details |
|--------|---------|
| **Protocol** | MQTT over TLS |
| **Detection** | Source is always `player` for MQTT views |
| **Device type** | Always `player` |
| **Auth** | Required (player registration) |
| **Metadata** | Partial (no country, includes channel context) |
| **Rate limit** | 1 view per 5 seconds per device |

### Source: Widget

Views from embedded Makapix widgets on third-party websites.

| Aspect | Details |
|--------|---------|
| **Protocol** | HTTPS (cross-origin) |
| **Detection** | Special widget API endpoints |
| **Device types** | Desktop, mobile, tablet |
| **Auth** | Optional |
| **Metadata** | Full + referrer domain tracking |

### Source: API

Views from custom API integrations and third-party clients.

| Aspect | Details |
|--------|---------|
| **Protocol** | HTTPS |
| **Detection** | Based on API endpoint and user agent |
| **Device types** | Inferred from user agent |
| **Auth** | Varies by endpoint |
| **Metadata** | Full |

## Device Types

```mermaid
pie title Device Type Distribution (Example)
    "Desktop" : 45
    "Mobile" : 35
    "Tablet" : 10
    "Player" : 10
```

### Detection Algorithm

Device type is detected from the `User-Agent` header using regex pattern matching:

```
function detect_device_type(user_agent):
    if matches(PLAYER_PATTERNS):    // "Makapix-Player", "PixelFrame", "Divoom"
        return PLAYER
    
    if matches(TABLET_PATTERNS):    // "iPad", "Android" (without "Mobile")
        return TABLET
    
    if matches(MOBILE_PATTERNS):    // "iPhone", "Android.*Mobile", etc.
        return MOBILE
    
    return DESKTOP                   // Default
```

### Player Detection Patterns

Physical player devices are identified by custom User-Agent strings:

- `Makapix-Player/*`
- `PixelFrame/*`
- `Divoom/*`

### Mobile Detection Patterns

| Pattern | Examples |
|---------|----------|
| `iPhone` | Safari on iPhone |
| `iPod` | Safari on iPod Touch |
| `Android.*Mobile` | Chrome on Android phone |
| `Mobile.*Safari` | Generic mobile Safari |
| `webOS` | Palm/LG webOS |
| `BlackBerry` | BlackBerry browser |
| `Opera Mini/Mobi` | Opera Mobile |
| `IEMobile` | Internet Explorer Mobile |
| `Windows Phone` | Windows Phone browser |

### Tablet Detection Patterns

| Pattern | Examples |
|---------|----------|
| `iPad` | Safari on iPad |
| `Android` (without `Mobile`) | Chrome on Android tablet |
| `Tablet` | Generic tablet UA |
| `PlayBook` | BlackBerry PlayBook |
| `Silk` | Amazon Silk browser |
| `Kindle` | Kindle browser |

## View Types (Intent Classification)

View type indicates **how** the user encountered the artwork:

```mermaid
flowchart LR
    subgraph Intentional["Intentional (Direct Action)"]
        CLICK[User clicked artwork]
        OPEN[User opened artwork page]
        SELECT[User selected on player]
    end
    
    subgraph Automated["Automated/Passive"]
        FEED[Appeared in feed]
        SEARCH[Appeared in search]
        PLAYLIST[Auto-played in playlist]
        WIDGET[Loaded in widget]
    end
```

### Type: Intentional

The user explicitly chose to view this artwork.

| Trigger | Example |
|---------|---------|
| Click on artwork card | User clicks thumbnail in gallery |
| Direct URL navigation | User visits `/p/{sqid}` directly |
| Player artwork selection | User presses button to view specific artwork |

### Type: Listing

The artwork appeared as part of a list or feed.

| Trigger | Example |
|---------|---------|
| Feed scroll | Artwork visible in "Recent Artworks" |
| Profile gallery | Artwork visible on artist's profile |
| Channel playback | Auto-playing in player channel |

### Type: Search

The artwork appeared in search results.

| Trigger | Example |
|---------|---------|
| Search results | Artwork matches search query |
| Hashtag browse | Artwork appears in hashtag listing |

### Type: Widget

The artwork was viewed through an embedded widget.

| Trigger | Example |
|---------|---------|
| GitHub Pages embed | Artwork in artist's GitHub gallery |
| Third-party embed | Widget on external blog |

## Player Channels

Physical player devices track the **channel** being played when a view occurs:

```mermaid
flowchart TD
    subgraph Channels
        ALL[all<br/>All public artworks]
        PROMOTED[promoted<br/>Promoted artworks only]
        USER[user<br/>Player owner's artworks]
        BY_USER[by_user<br/>Specific user's artworks]
        ARTWORK[artwork<br/>Single artwork mode]
        HASHTAG[hashtag<br/>Filtered by tag]
    end
    
    subgraph Context["Channel Context"]
        BY_USER --> |channel_context| SQID[user_sqid]
        HASHTAG --> |channel_context| TAG[hashtag string]
    end
```

### Channel: all

All publicly visible artworks from all users.

### Channel: promoted

Only artworks that have been promoted (frontpage, editor-pick, weekly-pack).

### Channel: user

The player owner's own artworks.

### Channel: by_user

A specific user's artworks. Requires `channel_context` containing the target user's `public_sqid`.

### Channel: artwork

Single artwork mode (no automatic advancement).

### Channel: hashtag

Artworks filtered by a specific hashtag. Requires `channel_context` containing the hashtag (without `#`).

## Play Order Modes

Players can use different ordering strategies:

| Mode | Value | Description |
|------|-------|-------------|
| Server | `0` | Default server ordering (by ID/insertion) |
| Created | `1` | Chronological by creation date |
| Random | `2` | Randomized order (with optional seed) |

## Intent Mapping (Player)

Players report intent as either `artwork` or `channel`:

```mermaid
flowchart LR
    subgraph "Player Reports"
        P_ARTWORK[intent: artwork]
        P_CHANNEL[intent: channel]
    end
    
    subgraph "Legacy Values"
        L_INTENTIONAL[intentional]
        L_AUTOMATED[automated]
    end
    
    subgraph "Server Maps To"
        V_INTENTIONAL[ViewType.INTENTIONAL]
        V_LISTING[ViewType.LISTING]
    end
    
    P_ARTWORK --> V_INTENTIONAL
    P_CHANNEL --> V_LISTING
    L_INTENTIONAL --> V_INTENTIONAL
    L_AUTOMATED --> V_LISTING
```

The server accepts both old (`intentional`/`automated`) and new (`artwork`/`channel`) intent values for backward compatibility.

## Author View Exclusion

Views by the artwork's owner are **excluded** from tracking:

```mermaid
flowchart TD
    VIEW[View event]
    VIEW --> AUTH{User authenticated?}
    AUTH -->|No| RECORD[Record view]
    AUTH -->|Yes| CHECK{User == Post owner?}
    CHECK -->|No| RECORD
    CHECK -->|Yes| SKIP[Skip recording]
```

This ensures artists don't inflate their own view counts.

## Geographic Data

Country codes are resolved via GeoIP lookup from the viewer's IP address:

- Uses MaxMind GeoLite2 database
- Returns ISO 3166-1 alpha-2 codes (e.g., `US`, `BR`, `JP`)
- Falls back to `null` if lookup fails
- Not available for player views (players don't expose IP)

### Top Countries Display

The stats UI shows the top 10 countries by view count with:
- Country flag emoji (derived from code)
- Full country name mapping
- View count and relative bar chart

---

*See also: [Player Integration](./player-integration.md) for MQTT protocol details*

