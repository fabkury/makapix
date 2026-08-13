# Makapix Club

Glossary for the Makapix Club (MPX) domain — a pixel art social network serving web browsers, a mobile app, and physical player devices. Terms below are canonical; code and docs should converge on them.

## Artwork engagement

**Artwork View**:
A person deliberately looked at an artwork: on screen at least 2 seconds, by a Visitor who is not the artwork's author, counted at most once per Visitor per artwork per UTC day. The only metric public counters show.
_Avoid_: view (unqualified), intentional view, hit

**Impression**:
An artwork passed in front of someone without a deliberate choice to look — autoplay rotation on a player or Web Player, or appearance in a listing. Counted as volume, never summed with Artwork Views.
_Avoid_: listing view, passive view, play

**Visitor**:
The deduplication identity behind view metrics: the user account when authenticated, otherwise the (salted) hashed IP. One person on two logged-in devices is one Visitor; a shared anonymous NAT is one Visitor.
_Avoid_: viewer (when identity is meant), unique

**Unique Viewers**:
The number of distinct Visitors in a window. Exact within a single day; any cross-day figure is an approximation and must be labeled as such.

## Devices

**Player**:
A physical pixel-art display device (e.g. p3a) owned by a user. A Player's engagement is attributed to its owner as an authenticated Visitor; its views of the owner's own artworks are excluded as self-views.
_Avoid_: frame, device (unqualified)

**Web Player**:
The in-browser fullscreen autoplay mode that rotates through a channel, emulating a Player.
