#!/bin/sh
# Guard: the web app never uses the browser's native date pickers — use <DatePicker> from "@/ui".
# Fails if a native date/time input appears anywhere in apps/web/src outside ui/DatePicker.tsx.
cd "$(dirname "$0")/.." || exit 2
HITS=$(grep -rnE "type=\{?[\"'](date|datetime-local|month|week|time)[\"']" apps/web/src --include='*.ts' --include='*.tsx' \
  | grep -v "apps/web/src/ui/DatePicker.tsx")
if [ -n "$HITS" ]; then
  echo "Native date input found — use <DatePicker> from \"@/ui\" instead:"
  echo "$HITS"
  exit 1
fi
echo "OK: no native date inputs in apps/web/src"
