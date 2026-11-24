#!/bin/sh
# Guard: the web app never shows the browser's native pickers — dates go through <DatePicker>, choices through <Select>
# (both from "@/ui"). Fails if a native date/time input or a native <select> appears in apps/web/src outside its primitive.
cd "$(dirname "$0")/.." || exit 2
FAIL=0
DATE_HITS=$(grep -rnE "type=\{?[\"'](date|datetime-local|month|week|time)[\"']" apps/web/src --include='*.ts' --include='*.tsx' \
  | grep -v "apps/web/src/ui/DatePicker.tsx")
if [ -n "$DATE_HITS" ]; then
  echo "Native date input found — use <DatePicker> from \"@/ui\" instead:"
  echo "$DATE_HITS"
  FAIL=1
fi
SELECT_HITS=$(grep -rnE "<select([[:space:]>/]|$)|createElement\([\"']select[\"']" apps/web/src --include='*.ts' --include='*.tsx' \
  | grep -v "apps/web/src/ui/input.tsx")
if [ -n "$SELECT_HITS" ]; then
  echo "Native <select> found — use <Select> from \"@/ui\" instead:"
  echo "$SELECT_HITS"
  FAIL=1
fi
[ "$FAIL" -eq 0 ] && echo "OK: no native date inputs or selects in apps/web/src"
exit "$FAIL"
