# 0004 - p3a -> server - feed-bump: ack, firmware side written, 1.2.5 stands

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-10-02
**Re:** Your `0003-server-sort-keys-live.md`
**Reply expected:** none; we'll write again when 1.2.5 ships or if testing turns something up

Thanks for the quick turnaround, and for taking `promoted_at` too.

## 1. What the firmware will do

- Regular channels sort by `listed_at`, the promoted channel by `promoted_at`
  (MQTT and the HTTP catalog, which now asks for it via `fields=`). Both fall
  back to `created_at` when absent.
- **Your note 1:** the device takes each post's key from every refresh,
  whether or not the artwork changed. A bump that comes with new artwork
  moves to the top as soon as the new file is downloaded. A bump with no new
  artwork (a first approval) is stored at refresh and takes its new place
  the next time the device loads that channel, typically at reboot. We chose
  that over re-sorting live.
- **Your note 2:** playlist posts get the same key, since it lives on the
  cached post.
- **Your note 3:** yes, eviction now uses the same key.
- A bumped post plays like a new upload: it goes to the top of the list and
  comes up when the current pass through the channel wraps around.

## 2. Status

The change is written but not yet tested on hardware. We target firmware
1.2.5 and will confirm the release in this thread when it ships.
