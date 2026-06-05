#!/usr/bin/env python3
"""Apply a SQL migration file to Supabase via the Management API.

Usage: python3 scripts/apply_sql_migration.py <path-to-sql> [--dry-run]

Env: SUPABASE_PAT (personal access token), SUPABASE_URL (https://<ref>.supabase.co)

Extracted from .github/workflows/apply-migration.yml, where it lived as an inline
`python3 -c "..."` heredoc whose un-indented body broke the YAML block scalar and
caused a startup_failure on every push. Keeping it as a real file avoids the
YAML/Python indentation conflict entirely.
"""
import json
import os
import sys
import urllib.request


def main() -> int:
    args = [a for a in sys.argv[1:] if a]
    dry_run = "--dry-run" in args
    paths = [a for a in args if a != "--dry-run"]
    if not paths:
        print("usage: apply_sql_migration.py <path-to-sql> [--dry-run]", file=sys.stderr)
        return 2
    sql_path = paths[0]

    supabase_url = os.environ["SUPABASE_URL"]
    project_ref = supabase_url.replace("https://", "").split(".supabase.co")[0]
    sql = open(sql_path).read()

    print(f"Project ref: {project_ref}")
    print(f"Migration file: {sql_path}")
    print("--- SQL ---")
    print(sql)
    print("--- end SQL ---")
    if dry_run:
        print("DRY RUN — not executing")
        return 0

    pat = os.environ["SUPABASE_PAT"]
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            body = json.loads(r.read())
            print("Migration applied successfully")
            if isinstance(body, list):
                for row in body:
                    print(row)
            else:
                print(body)
    except urllib.request.HTTPError as e:
        err = e.read().decode()
        print(f"HTTP {e.code}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
