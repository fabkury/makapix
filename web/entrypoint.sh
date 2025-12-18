#!/bin/sh
set -eu

# This container is used for remote VPS deployment. During deploys, clients may
# temporarily have cached HTML that references older hashed Next.js chunks.
# If we delete old chunks on each deploy, those clients will get 404s and the
# page will appear "broken" (especially on mobile).
#
# To make deploys backward-compatible, we mount a persistent Docker volume at
# /app/.next/static and *merge* the current build's static assets into it at
# startup without deleting existing files.

mkdir -p /app/.next/static

# Ensure the runtime user can read the directory. (Volume may be root-owned)
chown -R nextjs:nodejs /app/.next || true

# Merge current build assets into the persistent static dir (do NOT delete old).
# -p: preserve mode where possible, -R: recursive, -f: overwrite same-name files.
cp -pR /opt/next-static/. /app/.next/static/ 2>/dev/null || cp -R /opt/next-static/. /app/.next/static/

# Drop privileges for the actual server process.
exec su-exec nextjs:nodejs "$@"


