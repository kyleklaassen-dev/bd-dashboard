#!/usr/bin/env python3
"""Deploy one or more repo files to GitHub (Git Data API, single commit).

Usage:
  GITHUB_TOKEN=... python3 scripts/deploy_files.py "commit message" path1 [path2 ...]

Paths are relative to the repo root. Reads token from $GITHUB_TOKEN or .github_token.
Used because git on the mounted workspace is unreliable — deploy via API instead.
"""
import os, sys, base64, requests, pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN = os.environ.get("GITHUB_TOKEN") or (REPO_ROOT / ".github_token").read_text().strip()
REPO  = os.environ.get("GITHUB_REPO", "kyleklaassen-dev/bd-dashboard")
API   = f"https://api.github.com/repos/{REPO}"
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28"}


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: deploy_files.py 'message' path1 [path2 ...]")
    msg, paths = sys.argv[1], sys.argv[2:]

    head = requests.get(f"{API}/git/ref/heads/main", headers=H, timeout=20)
    head.raise_for_status()
    head_sha = head.json()["object"]["sha"]
    base_tree = requests.get(f"{API}/git/commits/{head_sha}", headers=H, timeout=20).json()["tree"]["sha"]

    tree = []
    for rel in paths:
        data = (REPO_ROOT / rel).read_bytes()
        blob = requests.post(f"{API}/git/blobs", headers=H, timeout=60, json={
            "content": base64.b64encode(data).decode(), "encoding": "base64"})
        blob.raise_for_status()
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob.json()["sha"]})
        print(f"  blob {rel}: {len(data)} bytes")

    new_tree = requests.post(f"{API}/git/trees", headers=H, timeout=30,
                             json={"base_tree": base_tree, "tree": tree})
    new_tree.raise_for_status()
    commit = requests.post(f"{API}/git/commits", headers=H, timeout=30, json={
        "message": msg, "tree": new_tree.json()["sha"], "parents": [head_sha]})
    commit.raise_for_status()
    new_sha = commit.json()["sha"]
    ref = requests.patch(f"{API}/git/refs/heads/main", headers=H, timeout=30,
                         json={"sha": new_sha, "force": False})
    ref.raise_for_status()
    print(f"Deployed {len(paths)} file(s) → commit {new_sha[:7]}")


if __name__ == "__main__":
    main()
