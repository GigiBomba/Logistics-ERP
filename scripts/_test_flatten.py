#!/usr/bin/env python3
"""Test flatten/unflatten with lists."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from translate_batch2 import flatten, unflatten

# Test 1: Simple list
test1 = {"main": {"currencies": ["EUR", "RON"]}}
flat1 = flatten(test1)
print("Test 1 - flat:", dict(flat1))
new1 = unflatten(flat1)
print("Test 1 - new:", new1)
print("Test 1 - currencies type:", type(new1["main"]["currencies"]).__name__)
assert isinstance(new1["main"]["currencies"], list), "List was NOT preserved!"
print("Test 1 PASS")

# Test 2: Load real cs.json
cs_path = os.path.join(os.path.dirname(__file__), "..", "data", "translations", "cs.json")
d = json.load(open(cs_path, "r", encoding="utf-8-sig"))
flat2 = flatten(d)
has_currencies = "main.currencies" in flat2
print("Test 2 - has main.currencies:", has_currencies)
if has_currencies:
    print("  type:", type(flat2["main.currencies"]).__name__)
    print("  val:", flat2["main.currencies"])

# Check for currencies[0] keys
bad_keys = [k for k in flat2 if "currencies[" in k]
print("  bad keys (currencies[N]):", bad_keys[:5])

new2 = unflatten(flat2)
m = new2.get("main", {})
has_curr_list = "currencies" in m
print("Test 2 - new has currencies list:", has_curr_list)
if has_curr_list:
    print("  type:", type(m["currencies"]).__name__)
    print("  val:", m["currencies"])

# Test 3: Save and reload
import tempfile
tmp = tempfile.mktemp(suffix=".json")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(new2, f, ensure_ascii=False, indent=2)
    f.write("\n")
reloaded = json.load(open(tmp, "r", encoding="utf-8"))
m3 = reloaded.get("main", {})
has_curr_list3 = "currencies" in m3
print("Test 3 - reloaded has currencies list:", has_curr_list3)
if has_curr_list3:
    print("  type:", type(m3["currencies"]).__name__)
    print("  val:", m3["currencies"])
os.unlink(tmp)
