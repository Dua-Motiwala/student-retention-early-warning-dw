"""
===============================================================================
Module: etl/backup.py
Phase: All Phases (Backup & Versioning Utility)
Purpose: Automates mysqldump backups and file snapshots without Git, 
         strictly following security rules (no password logging).
Usage:
    python etl/backup.py --phase phase1_setup_done
===============================================================================
"""

import os
import sys
import shutil
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import get_db_config


def perform_backup(phase_tag: str):
    """
    Creates a mysqldump backup and a code snapshot.
    
    Args:
        phase_tag (str): Identifier for the phase (e.g. 'phase1_setup_done').
    """
    cfg = get_db_config()
    backups_dir = PROJECT_ROOT / "backups"
    backups_dir.mkdir(exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    snapshot_name = f"{phase_tag}_{date_str}"
    dump_filename = backups_dir / f"{phase_tag.split('_')[0]}.sql"
    
    print("=" * 70)
    print(f"CREATING BACKUP: {snapshot_name}")
    print("=" * 70)

    # 1. mysqldump execution
    # Locate mysqldump binary
    mysql_bin_dir = os.getenv("MYSQL_BIN_DIR", r"C:\Program Files\MySQL\MySQL Server 8.0\bin")
    mysqldump_exe = Path(mysql_bin_dir) / "mysqldump.exe"
    if not mysqldump_exe.exists():
        mysqldump_cmd = "mysqldump"
    else:
        mysqldump_cmd = str(mysqldump_exe)

    schemas = ["staging", "bronze", "silver", "gold", "marts"]
    
    dump_args = [
        mysqldump_cmd,
        f"-h{cfg['host']}",
        f"-P{cfg['port']}",
        f"-u{cfg['user']}",
        "--databases"
    ] + schemas

    # Set password via environment variable to avoid printing in logs/process table
    env = os.environ.copy()
    if cfg["password"]:
        env["MYSQL_PWD"] = cfg["password"]

    print(f"Exporting database dump to: {dump_filename.name}...")
    try:
        with open(dump_filename, "w", encoding="utf-8") as out_f:
            res = subprocess.run(dump_args, stdout=out_f, stderr=subprocess.PIPE, text=True, env=env)
        if res.returncode == 0:
            print(f"[OK] Database dump created successfully: {dump_filename.name}")
        else:
            print(f"[WARNING] mysqldump finished with code {res.returncode}: {res.stderr.strip()}")
    except Exception as e:
        print(f"[ERROR] mysqldump failed: {e}")

    # 2. File snapshot (excluding data/raw/*.csv, .env, and backups directory)
    snapshot_dir = backups_dir / snapshot_name
    print(f"Creating project snapshot in: {snapshot_dir.relative_to(PROJECT_ROOT)}...")
    
    def ignore_patterns(folder, names):
        ignored = set()
        folder_path = Path(folder)
        # Exclude backups directory itself to prevent recursive bloat
        if folder_path == PROJECT_ROOT:
            ignored.add("backups")
            ignored.add(".env")
            ignored.add(".git")
            ignored.add("__pycache__")
        # Exclude heavy CSV files inside data/raw
        if folder_path == PROJECT_ROOT / "data" / "raw":
            for n in names:
                if n.endswith(".csv"):
                    ignored.add(n)
        for n in names:
            if n in [".git", "__pycache__", ".ipynb_checkpoints"]:
                ignored.add(n)
        return ignored

    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
        
    shutil.copytree(PROJECT_ROOT, snapshot_dir, ignore=ignore_patterns)
    print(f"[OK] Project code snapshot created successfully: {snapshot_name}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup utility for DWBI Project")
    parser.add_argument("--phase", type=str, default="phase1_setup_done", help="Phase tag for backup")
    args = parser.parse_args()
    perform_backup(args.phase)
