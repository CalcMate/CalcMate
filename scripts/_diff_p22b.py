import os, difflib

old_dir = "data/workspace/_site_p22b_final"
new_dir = "data/workspace/_site"

diffs = []
for root, dirs, files in os.walk(new_dir):
    for fname in files:
        rel = os.path.relpath(os.path.join(root, fname), new_dir)
        old_path = os.path.join(old_dir, rel)
        new_path = os.path.join(root, fname)
        if not os.path.exists(old_path):
            diffs.append("NEW FILE: " + rel)
            continue
        try:
            old_content = open(old_path, encoding="utf-8").readlines()
            new_content = open(new_path, encoding="utf-8").readlines()
        except Exception:
            continue
        d = list(difflib.unified_diff(old_content, new_content, fromfile="old/"+rel, tofile="new/"+rel, n=0))
        if d:
            diffs.append("".join(d[:80]))

if not diffs:
    print("DIFF: 0건 -- 완전 일치")
else:
    print("DIFF: " + str(len(diffs)) + "건")
    for d in diffs:
        print("---")
        print(d[:800])
