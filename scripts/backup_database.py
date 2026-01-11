#!/usr/bin/env python3
"""
数据库备份脚本

自动备份SQLite数据库，支持：
- 定时备份
- 备份保留策略
- 压缩备份
- 备份验证

用法:
    python scripts/backup_database.py
    python scripts/backup_database.py --retention-days 30
    python scripts/backup_database.py --compress
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.logger import get_logger
from src.core.defaults import PATHS

logger = get_logger("backup")


def backup_database(
    db_path: str,
    backup_dir: str,
    compress: bool = False,
    retention_days: int = 30
) -> str:
    """
    备份数据库
    
    Args:
        db_path: 数据库文件路径
        backup_dir: 备份目录
        compress: 是否压缩备份
        retention_days: 保留天数
    
    Returns:
        备份文件路径
    """
    os.makedirs(backup_dir, exist_ok=True)
    
    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = Path(db_path).stem
    backup_filename = f"{db_name}_backup_{timestamp}.db"
    
    if compress:
        backup_filename += ".gz"
    
    backup_path = os.path.join(backup_dir, backup_filename)
    
    logger.info(f"Backing up database: {db_path} -> {backup_path}")
    
    # 执行备份
    try:
        if compress:
            import gzip
            with open(db_path, "rb") as src, gzip.open(backup_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(db_path, backup_path)
        
        # 验证备份
        if verify_backup(backup_path, compress):
            logger.info(f"✓ Backup successful: {backup_path}")
            
            # 清理旧备份
            cleanup_old_backups(backup_dir, retention_days)
            
            return backup_path
        else:
            logger.error("✗ Backup verification failed")
            if os.path.exists(backup_path):
                os.remove(backup_path)
            raise Exception("Backup verification failed")
    
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        raise


def verify_backup(backup_path: str, compressed: bool = False) -> bool:
    """验证备份文件完整性"""
    try:
        if compressed:
            import gzip
            with gzip.open(backup_path, "rb") as f:
                # 读取前几个字节验证文件格式
                header = f.read(16)
                if not header.startswith(b"SQLite format"):
                    return False
        else:
            with open(backup_path, "rb") as f:
                header = f.read(16)
                if not header.startswith(b"SQLite format"):
                    return False
        
        # 尝试打开数据库
        if compressed:
            import tempfile
            import gzip
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                with gzip.open(backup_path, "rb") as src:
                    shutil.copyfileobj(src, tmp)
                tmp_path = tmp.name
            
            try:
                conn = sqlite3.connect(tmp_path)
                conn.execute("SELECT 1")
                conn.close()
                os.remove(tmp_path)
                return True
            except Exception:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                return False
        else:
            conn = sqlite3.connect(backup_path)
            conn.execute("SELECT 1")
            conn.close()
            return True
    
    except Exception as e:
        logger.error(f"Backup verification error: {e}")
        return False


def cleanup_old_backups(backup_dir: str, retention_days: int):
    """清理旧备份"""
    if not os.path.exists(backup_dir):
        return
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0
    
    for filename in os.listdir(backup_dir):
        if not filename.startswith("market_data_backup_"):
            continue
        
        file_path = os.path.join(backup_dir, filename)
        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        if file_time < cutoff_date:
            try:
                os.remove(file_path)
                deleted_count += 1
                logger.debug(f"Deleted old backup: {filename}")
            except Exception as e:
                logger.warning(f"Failed to delete {filename}: {e}")
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old backup(s)")


def get_backup_stats(backup_dir: str) -> dict:
    """获取备份统计信息"""
    if not os.path.exists(backup_dir):
        return {"count": 0, "total_size_mb": 0}
    
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith("market_data_backup_"):
            file_path = os.path.join(backup_dir, filename)
            backups.append({
                "filename": filename,
                "size": os.path.getsize(file_path),
                "modified": datetime.fromtimestamp(os.path.getmtime(file_path))
            })
    
    total_size = sum(b["size"] for b in backups)
    
    return {
        "count": len(backups),
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "backups": sorted(backups, key=lambda x: x["modified"], reverse=True)
    }


def main():
    parser = argparse.ArgumentParser(description="数据库备份工具")
    parser.add_argument("--db-path", default=PATHS["database"],
                       help="数据库文件路径")
    parser.add_argument("--backup-dir", default="./backups",
                       help="备份目录")
    parser.add_argument("--compress", action="store_true",
                       help="压缩备份文件")
    parser.add_argument("--retention-days", type=int, default=30,
                       help="备份保留天数")
    parser.add_argument("--stats", action="store_true",
                       help="显示备份统计信息")
    
    args = parser.parse_args()
    
    if args.stats:
        stats = get_backup_stats(args.backup_dir)
        print(f"\n备份统计:")
        print(f"  备份数量: {stats['count']}")
        print(f"  总大小: {stats['total_size_mb']} MB")
        if stats['backups']:
            print(f"\n最近的备份:")
            for backup in stats['backups'][:5]:
                size_mb = backup['size'] / 1024 / 1024
                print(f"  {backup['filename']} ({size_mb:.2f} MB, {backup['modified'].strftime('%Y-%m-%d %H:%M:%S')})")
        return
    
    if not os.path.exists(args.db_path):
        logger.error(f"Database not found: {args.db_path}")
        sys.exit(1)
    
    try:
        backup_path = backup_database(
            args.db_path,
            args.backup_dir,
            compress=args.compress,
            retention_days=args.retention_days
        )
        print(f"\n✓ Backup completed: {backup_path}")
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
