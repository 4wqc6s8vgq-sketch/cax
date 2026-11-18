#!/usr/bin/env bash
# Collect real coverage for one Defects4J buggy revision. Does not compute formal EG-TEP scores.
set -Eeuo pipefail
PROJECT="${1:-Codec}"
BUG="${2:-1}"
case "$PROJECT" in Codec|Csv) ;; *) echo "Only frozen-pilot Codec/Csv projects accepted" >&2; exit 2;; esac
[[ "$BUG" =~ ^[1-9][0-9]*$ ]] || { echo "Invalid bug ID" >&2; exit 2; }
: "${D4J_HOME:?Set D4J_HOME to initialized Defects4J installation}"
: "${GZOLTAR_CLI_JAR:?Set GZOLTAR_CLI_JAR}"
: "${GZOLTAR_AGENT_JAR:?Set GZOLTAR_AGENT_JAR}"
[[ -f "$GZOLTAR_CLI_JAR" && -f "$GZOLTAR_AGENT_JAR" ]] || { echo "GZoltar JAR missing" >&2; exit 2; }
command -v defects4j >/dev/null || { echo "Defects4J CLI missing" >&2; exit 2; }
command -v javac >/dev/null || { echo "Javac missing" >&2; exit 2; }
export TZ=America/Los_Angeles
ROOT="${EGTEP_OUTPUT:-$PWD/results}"
mkdir -p "$ROOT"
ROOT="$(cd "$ROOT" && pwd)"
RUN="$ROOT/${PROJECT}-${BUG}b"
mkdir -p "$RUN"/{raw,logs,metadata,labels_sealed}
# Explicit status: completion is only declared by the independent validator.
printf 'RUN_IN_PROGRESS\n' > "$RUN/STATUS.txt"
trap 'r=$?; if [[ $r -ne 0 ]]; then printf "BLOCKED_EXIT_%s\n" "$r" > "$RUN/STATUS.txt"; fi' EXIT
{
  date -u '+UTC=%FT%TZ'
  java -version 2>&1
  javac -version 2>&1
  defects4j -h 2>&1 | head -n 8 || true
  git -C "$D4J_HOME" rev-parse HEAD
  printf 'project=%s\nbug=%s\nTZ=%s\n' "$PROJECT" "$BUG" "$TZ"
} > "$RUN/metadata/environment.txt"
WORK="$RUN/checkout_buggy"
if [[ -e "$WORK" ]]; then echo "Refusing to overwrite existing checkout: $WORK" >&2; exit 3; fi
# All candidates are collected from the buggy revision's compiled production classes only.
defects4j checkout -p "$PROJECT" -v "${BUG}b" -w "$WORK" > "$RUN/logs/checkout.log" 2>&1
(git -C "$WORK" rev-parse HEAD || svn info "$WORK" || echo "REVISION_IDENTIFICATION_UNAVAILABLE") > "$RUN/metadata/buggy_revision.txt" 2>&1
defects4j info -p "$PROJECT" -b "$BUG" > "$RUN/metadata/bug_info.txt" 2> "$RUN/logs/bug_info.err" || true
(
 cd "$WORK"
 defects4j compile > "$RUN/logs/compile.log" 2>&1
 # A failing test suite is expected for the buggy revision; preserve its actual exit code.
 set +e; defects4j test > "$RUN/logs/test_full.log" 2>&1; rc=$?; set -e
 printf '%s\n' "$rc" > "$RUN/metadata/test_full_exit_code.txt"
 [[ -f failing_tests ]] && cp failing_tests "$RUN/raw/defects4j_failing_tests.txt"
 for prop in dir.src.classes dir.bin.classes dir.bin.tests cp.test tests.all tests.trigger classes.modified; do
    # Sealed ground-truth metadata is not used to select candidate classes or tests.
    if [[ "$prop" = "classes.modified" ]]; then target="$RUN/labels_sealed"; else target="$RUN/metadata"; fi
    defects4j export -p "$prop" > "$target/${prop}.txt" 2> "$RUN/logs/export_${prop//./_}.err" || true
 done
)
SRC_REL="$(cat "$RUN/metadata/dir.src.classes.txt")"
BIN_REL="$(cat "$RUN/metadata/dir.bin.classes.txt")"
TST_REL="$(cat "$RUN/metadata/dir.bin.tests.txt")"
TEST_CP="$(cat "$RUN/metadata/cp.test.txt")"
[[ -n "$SRC_REL" && -n "$BIN_REL" && -n "$TST_REL" && -n "$TEST_CP" ]] || { echo "Defects4J export incomplete" >&2; exit 4; }
[[ -d "$WORK/$SRC_REL" && -d "$WORK/$BIN_REL" && -d "$WORK/$TST_REL" ]] || { echo "Exported directories missing" >&2; exit 4; }
# Snapshot same-revision production sources and hashes before any evaluation-label processing.
( cd "$WORK"; tar -czf "$RUN/raw/buggy_production_sources.tar.gz" "$SRC_REL" )
( cd "$WORK/$SRC_REL"; find . -type f -name '*.java' -print0 | sort -z | xargs -0 -r sha256sum ) > "$RUN/raw/buggy_java_sha256.txt"
find "$WORK/$BIN_REL" -type f -name '*.class' | sed "s|^$WORK/$BIN_REL/||;s|/|.|g;s|\.class$||" | grep -v -E '(^|\.)(module-info|package-info)$' | LC_ALL=C sort -u > "$RUN/raw/all_buggy_production_classes.txt"
[[ -s "$RUN/raw/all_buggy_production_classes.txt" ]] || { echo "Empty production class candidate universe" >&2; exit 5; }
# GZoltar's colon-separated class include list; derived without looking at fixed patch/modified classes.
CLASS_FILTER="$(paste -sd: "$RUN/raw/all_buggy_production_classes.txt")"
CLASS_FILTER="$CLASS_FILTER:"
TEST_METHODS="$RUN/raw/gzoltar_test_methods.txt"
JAVA_CP="$TEST_CP:$WORK/$BIN_REL:$WORK/$TST_REL:$GZOLTAR_CLI_JAR"
(
 cd "$WORK"
 java -cp "$JAVA_CP" com.gzoltar.cli.Main listTestMethods "$WORK/$TST_REL" --outputFile "$TEST_METHODS" --includes '*' \
   > "$RUN/logs/gzoltar_list_tests.log" 2>&1
)
[[ -s "$TEST_METHODS" ]] || { echo "No test methods listed" >&2; exit 6; }
SER="$RUN/raw/gzoltar.ser"
(
 cd "$WORK"
 java "-javaagent:${GZOLTAR_AGENT_JAR}=destfile=${SER},buildlocation=${WORK}/${BIN_REL},includes=${CLASS_FILTER},excludes=,inclnolocationclasses=false,output=FILE" \
    -cp "$JAVA_CP" com.gzoltar.cli.Main runTestMethods --testMethods "$TEST_METHODS" --collectCoverage \
    > "$RUN/logs/gzoltar_run_tests.log" 2>&1
)
[[ -s "$SER" ]] || { echo "GZoltar did not create serialized coverage" >&2; exit 7; }
(
 cd "$WORK"
 java -cp "$JAVA_CP" com.gzoltar.cli.Main faultLocalizationReport \
   --buildLocation "$WORK/$BIN_REL" --granularity line \
   --inclPublicMethods --inclStaticConstructors --inclDeprecatedMethods \
   --dataFile "$SER" --outputDirectory "$RUN/raw" \
   --family sfl --formula ochiai --metric entropy --formatter txt \
   > "$RUN/logs/gzoltar_report.log" 2>&1
)
TXT="$RUN/raw/sfl/txt"
[[ -s "$TXT/tests.csv" && -s "$TXT/spectra.csv" && -s "$TXT/matrix.txt" ]] || { echo "Missing per-test spectrum evidence" >&2; exit 8; }
# The data-quality gate is in a separate Python implementation.
python3 "${EGTEP_KIT_DIR:-$(dirname "$0")/..}/scripts/validate_spectra.py" \
   --directory "$TXT" --candidate-file "$RUN/raw/all_buggy_production_classes.txt" \
   --out "$RUN/metadata/spectrum_audit.json" \
   --listed-tests "$TEST_METHODS" \
   --trigger-tests "$RUN/metadata/tests.trigger.txt" \
   --execution-log "$RUN/logs/gzoltar_run_tests.log"
# A partial discovered test population must not be marked as full coverage.
if python3 - "$RUN/metadata/spectrum_audit.json" <<'PY_EGTEP_STATUS'
import json,sys
r=json.load(open(sys.argv[1],encoding='utf8'))
sys.exit(0 if r.get('status')=='INPUT_STRUCTURE_VALID' else 1)
PY_EGTEP_STATUS
then
  printf 'RAW_REAL_COVERAGE_COLLECTED_E01_LABEL_AUDIT_PENDING\n' > "$RUN/STATUS.txt"
else
  printf 'RAW_REAL_COVERAGE_EXPORT_GAPS_E01_BLOCKED\n' > "$RUN/STATUS.txt"
fi
( cd "$RUN"; find raw logs metadata labels_sealed -type f -print0 | sort -z | xargs -0 -r sha256sum ) > "$RUN/FILE_SHA256.txt"
echo "Evidence collected in $RUN (E01 not yet formally accepted)"
