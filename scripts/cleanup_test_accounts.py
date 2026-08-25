"""Optional, explicit cleanup for previously polluted test accounts.

This script is NOT run automatically by tests. Review the printed list first,
then re-run with --execute to delete only known test-created account rows.
It does not delete browser profile folders; move/delete those manually only after
you are sure they are not real accounts.
"""
import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'database' / 'midasbuy.sqlite3'
TEST_NAMES = {'Test', 'Path Test One', 'Path Test Two', 'Test Account 001', 'Isolated Test Account', 'Regression Isolation Account'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Actually delete matching test account rows')
    args = parser.parse_args()
    if not DB.exists():
        print(f'Runtime database not found: {DB}')
        return
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        f"SELECT id, display_name, profile_path FROM accounts WHERE display_name IN ({','.join('?' for _ in TEST_NAMES)}) ORDER BY id",
        tuple(TEST_NAMES),
    ).fetchall()
    print('Matching likely test-created accounts:')
    for row in rows:
        print(row)
    if not args.execute:
        print('Dry run only. Re-run with --execute to delete these database rows.')
        conn.close(); return
    conn.execute(
        f"DELETE FROM accounts WHERE display_name IN ({','.join('?' for _ in TEST_NAMES)})",
        tuple(TEST_NAMES),
    )
    conn.commit(); conn.close()
    print(f'Deleted {len(rows)} test account rows. Browser profile folders were not deleted.')

if __name__ == '__main__':
    main()
