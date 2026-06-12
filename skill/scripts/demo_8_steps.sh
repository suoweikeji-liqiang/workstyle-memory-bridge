#!/usr/bin/env bash
# Contest submission structure wrapper: the canonical 8-step script lives at
# the repo root so all docs reference one copy. This forwards to it.
exec bash "$(dirname "$0")/../../scripts/demo_8_steps.sh" "$@"
