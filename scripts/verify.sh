#!/usr/bin/env bash
# One command, no wallet, no account. Re-runs the tests and reads the live deployment.
# Exit code is non-zero on the first failed claim.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.foundry/bin:$PATH"

fail=0
pass() { printf 'PASS  %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; fail=1; }

command -v forge >/dev/null || { echo "install foundry first: https://foundry.paradigm.xyz"; exit 1; }

echo "== build"
if forge build >/dev/null 2>&1; then pass "contracts compile"; else bad "contracts do not compile"; fi

echo "== tests"
if forge test >/dev/null 2>&1; then pass "test suite green"; else bad "test suite red (run forge test)"; fi

echo "== live deployment"
read -r BASE_POOL UNI_POOL GUARD BASE_PROXY UNI_PROXY < <(python3 - <<'PY'
import json
d = json.load(open("demo.json"))
print(d["base"]["pool"], d["uni"]["pool"], d["guard"]["address"], d["base"]["proxy"], d["uni"]["proxy"])
PY
)

code_len() { cast code "$1" --rpc-url "$2" | wc -c; }

[ "$(code_len "$BASE_POOL" https://sepolia.base.org)" -gt 10 ] && pass "base venue has code" || bad "base venue missing"
[ "$(code_len "$UNI_POOL" https://sepolia.unichain.org)" -gt 10 ] && pass "uni venue has code" || bad "uni venue missing"
[ "$(code_len "$GUARD" https://lasna-rpc.rnk.dev/)" -gt 10 ] && pass "guard has code on Lasna" || bad "guard missing"

base_price=$(cast call "$BASE_POOL" "price()(uint256)" --rpc-url https://sepolia.base.org 2>/dev/null | awk '{print $1}')
uni_price=$(cast call "$UNI_POOL" "price()(uint256)" --rpc-url https://sepolia.unichain.org 2>/dev/null | awk '{print $1}')
[ -n "$base_price" ] && [ "$base_price" != "0" ] && pass "base venue answers price()" || bad "base venue silent"
[ -n "$uni_price" ] && [ "$uni_price" != "0" ] && pass "uni venue answers price()" || bad "uni venue silent"

base_paused=$(cast call "$BASE_POOL" "paused()(bool)" --rpc-url https://sepolia.base.org 2>/dev/null | awk '{print $1}')
uni_paused=$(cast call "$UNI_POOL" "paused()(bool)" --rpc-url https://sepolia.unichain.org 2>/dev/null | awk '{print $1}')
[ "$base_paused" = "true" ] && pass "base venue is paused by the guard" || echo "NOTE  base venue is trading (fresh deployment, no attack yet)"
[ "$uni_paused" = "true" ] && pass "uni venue is paused by the guard" || echo "NOTE  uni venue is trading (fresh deployment, no attack yet)"

triggers=$(cast call "$GUARD" "triggers()(uint256)" --rpc-url https://lasna-rpc.rnk.dev/ 2>/dev/null | awk '{print $1}')
[ -n "$triggers" ] && pass "guard reports $triggers trip(s)" || bad "guard unreachable"

echo
if [ "$fail" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit "$fail"
