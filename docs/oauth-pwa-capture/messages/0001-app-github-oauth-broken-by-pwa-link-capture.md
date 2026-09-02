# 0001 — app → server: GitHub sign-in is broken on Android whenever the makapix.club PWA is installed

**From:** app team (makapix-app) · **Date:** 2026-08-27
**Severity:** GitHub sign-in fails **100%** on Android for any user who has installed makapix.club
as a PWA. Password sign-in is unaffected. iOS is unaffected.

This is **not** a device quirk and not caused by the zero-tap work — cause confirmed by an
enable/disable A/B on a real device. **We are holding the zero-tap release until this is resolved.**

## Symptom

Tap *Sign in with GitHub* → browser opens → GitHub authorization completes → **the app never
signs in.** The user is returned to a stalled splash screen and remains signed out. Reproduced 5×
across two different browsers.

## Root cause: the PWA captures the OAuth URLs

The native OAuth leg runs entirely on the apex origin:

```
start:     https://makapix.club/api/v1/auth/github/login
             ?redirect_uri=club.makapix.app://oauth/github&code_challenge=…&code_challenge_method=S256&state=…
callback:   https://makapix.club/api/auth/github/callback
             ?code=…&iss=https://github.com/login/oauth&state=…
```

An installed makapix.club PWA registers a **WebAPK** whose scope is `https://makapix.club/`, so it
claims those URLs. Android then has two handlers for them and the browser hands the navigation off
to the PWA mid-flow, ejecting it from the Custom Tab the app opened.

Once the flow is inside the PWA's task, the final `club.makapix.app://oauth/github` redirect
arrives from a **different task** than the one `flutter_web_auth_2` is waiting in. `CallbackActivity`
launches as its own task, shows a splash screen and never completes the pending request. The
callback *is* delivered — it just has nowhere to land.

### Activity traces

Failing (PWA enabled) — the WebAPK detour is steps 3–6:

```
1. app          → Chrome IntentDispatcher            https://makapix.club/…
2. Chrome       → CustomTabActivity                   ← correct so far
3. Chrome       → WebAPK H2OTransparentLauncherActivity   ← PWA captures the URL
4. WebAPK       → WebAPK SplashActivity
5. WebAPK       → Chrome WebappLauncherActivity       ACTION_START_WEBAPP
6. Chrome       → SameTaskWebApkActivity              webapp://webapk-…
7. …            → CallbackActivity                    orphaned task, stalls
```

Passing (same device, same build, PWA disabled — **nothing else changed**):

```
1. app          → Chrome IntentDispatcher            https://makapix.club/…
2. Chrome       → CustomTabActivity
3. Chrome       → CallbackActivity                   club.makapix.app://oauth/github  ✅ signs in
```

Handler resolution for `https://makapix.club/api/auth/github/callback`:

| PWA state | resolves to |
|---|---|
| enabled | `android/…ResolverActivity` — ambiguous, `isDefault=false`, `match=0x0` |
| disabled | `com.android.chrome/…IntentDispatcher` — unambiguous |

**Both browsers fail.** Microsoft Edge ejects to `ChromeTabbedActivity`; Chrome hands off to the
WebAPK directly. Different route, same outcome — so this is not browser-specific and switching
browsers is not a workaround.

## Ruled out

- **Not the zero-tap work.** The app build that signed in successfully at 14:11 today and the one
  failing at 16:54 differ only in a Kotlin `GetCredentialException` mapping that cannot touch OAuth.
- **Not the new apex `assetlinks.json`.** We checked: Android does **not** list `club.makapix.app`
  as a handler for `makapix.club` — only the WebAPK and the browser. The file added no claim, and
  our manifest declares no intent-filter for the apex. That change looks innocent.
- **Not App Links.** `app.makapix.club` and `app-dev.makapix.club` are both still `verified`.
- **Not process death.** The app process survives the whole flow; the pending request is lost to
  the task split, not to a restart.

The WebAPK has been installed since **2026-01-25**, which likely explains the long-standing
"GitHub login is glitchy on Android" reports — it would have been a race between the Custom Tab and
the PWA's link capture that users sometimes won. We can't prove that retrospectively, but it fits.

## The fix we'd like: move the native OAuth leg off the apex origin

**Both** endpoints must move — moving only the GitHub callback is not enough, because the PWA can
capture the opening navigation just as easily. A WebAPK's scope is a same-origin path prefix, so any
**different origin** is permanently out of its reach.

Our suggestion is a dedicated **`auth.makapix.club`**, serving the native OAuth leg only:

```
https://auth.makapix.club/api/v1/auth/github/login      (opened by the app)
https://auth.makapix.club/api/auth/github/callback      (GitHub's redirect target)
```

We picked a dedicated host over reusing `app.makapix.club` deliberately: `app.makapix.club` could
itself become a PWA scope later, which would silently reintroduce exactly this bug. A host that
serves nothing but the auth leg can never be captured. Your call, though — anything off the apex
solves it, and reusing `app.makapix.club` would be cheaper (it already has DNS, a cert and
assetlinks).

Knock-on items you'll know better than us:

- The **GitHub OAuth app's registered callback URL** has to change to the new host.
- The app pins these URLs in `ClubConfig`, so we ship a matching app release. **The app change is
  trivial and we can have it ready the moment you confirm the host** — but note that until users
  update, old installs keep using the apex and stay broken, so this needs an app release either way.
- Whether the website's own GitHub login should move too, or stay on the apex. It isn't affected —
  it runs *inside* the PWA scope, which is exactly where it wants to be.

We did **not** attempt an app-side workaround. The Custom Tab can't reliably refuse a WebAPK
hand-off, and papering over the orphaned-task symptom in the manifest would leave the capture in
place for every user. This wants fixing at the origin.

## What we need from you

1. Confirm the host you want (`auth.makapix.club`, `app.makapix.club`, or your own choice).
2. Serve the two endpoints there and update the GitHub OAuth app callback URL.
3. Reply here; we'll flip `ClubConfig` and roll it into the release we're currently holding.

Happy to test against dev first — `development.makapix.club` is reachable again since your fix.
