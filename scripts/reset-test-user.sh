#!/usr/bin/env bash
#
# reset-test-user.sh — delete a test account by email so you can re-register it.
#
# Useful for iterating on the registration flow without burning unique inboxes:
# register -> tweak -> reset -> register again with the SAME email.
#
# Uniqueness is enforced on users.email / users.email_normalized (see
# api/app/routers/auth.py and services/email_normalization.py), so dropping the
# user row (plus the FK children that would block it) frees the address.
#
# Targets the DB of whichever checkout this script lives in, mirroring the
# Makefile: /opt/makapix -> prod (makapix-prod), anything else -> dev (makapix-dev).
#
# Usage:
#   scripts/reset-test-user.sh you@example.com          # confirm interactively
#   scripts/reset-test-user.sh you@example.com -y        # skip the dev prompt
#   scripts/reset-test-user.sh -h
#
set -euo pipefail

usage() {
  sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//; /^set -euo/d'
  exit "${1:-0}"
}

EMAIL=""
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    -h|--help) usage 0 ;;
    -y|--yes)  ASSUME_YES=1 ;;
    -*)        echo "Unknown option: $arg" >&2; usage 1 ;;
    *)         EMAIL="$arg" ;;
  esac
done

[[ -n "$EMAIL" ]]      || { echo "error: email required" >&2; usage 1; }
[[ "$EMAIL" == *@* ]]  || { echo "error: '$EMAIL' is not an email address" >&2; exit 1; }

# --- locate repo + pick the compose stack the way the Makefile does ----------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="$REPO_ROOT/deploy/stack"

if [[ "$REPO_ROOT" == "/opt/makapix" ]]; then
  ENVNAME=prod; PROJECT=makapix-prod; ENVFILE=.env.prod; OVERLAY=docker-compose.prod.yml
else
  ENVNAME=dev;  PROJECT=makapix-dev;  ENVFILE=.env.dev;  OVERLAY=docker-compose.dev.yml
fi

COMPOSE=(docker compose -f docker-compose.yml -f "$OVERLAY" --env-file "$ENVFILE" -p "$PROJECT")
PSQL=("${COMPOSE[@]}" exec -T db psql -U owner -d makapix -v ON_ERROR_STOP=1 -v "email=$EMAIL")

cd "$STACK_DIR"

# --- preflight: show the account(s) that match ------------------------------
echo ">> stack: $PROJECT  (env=$ENVNAME)"
echo ">> looking up: $EMAIL"

MATCHES="$(
  "${PSQL[@]}" -tA -F '|' <<'SQL'
SELECT id, handle, email, email_verified
FROM users
WHERE lower(email) = lower(trim(:'email'))
   OR email_normalized = lower(trim(:'email'))
ORDER BY id;
SQL
)"

if [[ -z "${MATCHES//[$'\t\r\n ']/}" ]]; then
  echo ">> no matching user — email is already free to register."
  exit 0
fi

echo ">> match(es) found (id | handle | email | verified):"
echo "$MATCHES" | sed 's/^/     /'

# --- confirm ----------------------------------------------------------------
if [[ "$ENVNAME" == "prod" ]]; then
  echo "!! This is the PRODUCTION database."
  read -r -p "   Re-type the email to confirm deletion: " CONFIRM
  [[ "$CONFIRM" == "$EMAIL" ]] || { echo ">> aborted."; exit 1; }
elif [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p ">> Delete the above account(s)? [y/N] " CONFIRM
  [[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo ">> aborted."; exit 1; }
fi

# --- delete -----------------------------------------------------------------
# Pre-delete only the FK children that would BLOCK the users delete
# (NO ACTION / RESTRICT). CASCADE children are removed and SET NULL / SET DEFAULT
# children are nulled automatically by the final DELETE, so we leave those alone.
# Discovered dynamically from pg_constraint, so new tables are covered for free.
"${PSQL[@]}" <<'SQL'
BEGIN;
SELECT set_config('mpx.reset_email', lower(trim(:'email')), true);
DO $$
DECLARE
  v_email text := current_setting('mpx.reset_email');
  v_ids   int[];
  fk      record;
  n       bigint;
BEGIN
  SELECT array_agg(id) INTO v_ids
  FROM users
  WHERE lower(email) = v_email OR email_normalized = v_email;

  IF v_ids IS NULL THEN
    RAISE EXCEPTION 'no user found for %', v_email;
  END IF;

  RAISE NOTICE 'resetting user id(s): %', v_ids;

  FOR fk IN
    SELECT cl.relname AS child_table, att.attname AS child_col
    FROM pg_constraint con
    JOIN pg_class       cl    ON cl.oid    = con.conrelid
    JOIN pg_namespace   ns    ON ns.oid    = cl.relnamespace AND ns.nspname = 'public'
    JOIN pg_class       refcl ON refcl.oid = con.confrelid
    JOIN unnest(con.conkey) AS ck(attnum) ON true
    JOIN pg_attribute   att   ON att.attrelid = con.conrelid AND att.attnum = ck.attnum
    WHERE con.contype = 'f'
      AND refcl.relname = 'users'
      AND con.confdeltype IN ('a', 'r')   -- NO ACTION / RESTRICT only
  LOOP
    EXECUTE format('DELETE FROM %I WHERE %I = ANY($1)', fk.child_table, fk.child_col)
      USING v_ids;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
      RAISE NOTICE '  - %.%: deleted % row(s)', fk.child_table, fk.child_col, n;
    END IF;
  END LOOP;

  DELETE FROM users WHERE id = ANY(v_ids);
  RAISE NOTICE 'deleted % user row(s); email is now free to re-register.', array_length(v_ids, 1);
END $$;
COMMIT;
SQL

echo ">> done."
