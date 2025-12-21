#!/usr/bin/env python3
"""
Script de backup automatique des bases de données SQLite.
Crée des backups horodatés et nettoie les anciens backups.

Usage:
    python scripts/backup_databases.py

Cron (quotidien à 2h):
    0 2 * * * cd /app && python scripts/backup_databases.py
"""

import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backup_databases(
    data_dir: str = "data",
    backup_subdir: str = "backups",
    retention_count: int = 30
):
    """
    Backup toutes les bases SQLite dans data_dir.

    Args:
        data_dir: Répertoire contenant les DBs
        backup_subdir: Sous-répertoire pour les backups
        retention_count: Nombre de backups à garder par DB
    """
    data_path = Path(data_dir)
    backup_path = data_path / backup_subdir

    # Créer répertoire backup
    backup_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Répertoire backup: {backup_path}")

    # Timestamp pour ce backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Backup chaque fichier .db
    db_files = list(data_path.glob("*.db"))

    if not db_files:
        logger.warning("⚠️  Aucune base de données trouvée")
        return

    logger.info(f"🔍 {len(db_files)} base(s) de données trouvée(s)")

    for db_file in db_files:
        try:
            # Nom du backup avec timestamp
            backup_name = f"{db_file.stem}_{timestamp}.db"
            backup_file = backup_path / backup_name

            # Copier la DB
            shutil.copy2(db_file, backup_file)

            # Taille du backup
            size_mb = backup_file.stat().st_size / (1024 * 1024)

            logger.info(f"✅ Backup créé: {backup_name} ({size_mb:.2f} MB)")

        except Exception as e:
            logger.error(f"❌ Erreur backup {db_file.name}: {e}")

    # Nettoyage anciens backups
    cleanup_old_backups(backup_path, retention_count)


def cleanup_old_backups(backup_path: Path, retention_count: int):
    """
    Supprime les anciens backups en gardant les N plus récents par DB.

    Args:
        backup_path: Répertoire des backups
        retention_count: Nombre de backups à garder
    """
    logger.info(f"🧹 Nettoyage (conservation: {retention_count} backups)")

    # Grouper backups par nom de DB
    backups_by_db = {}

    for backup_file in backup_path.glob("*.db"):
        # Extraire nom DB (avant timestamp)
        # Format: dbname_YYYYMMDD_HHMMSS.db
        parts = backup_file.stem.rsplit('_', 2)
        if len(parts) >= 3:
            db_name = parts[0]
            if db_name not in backups_by_db:
                backups_by_db[db_name] = []
            backups_by_db[db_name].append(backup_file)

    # Nettoyer chaque DB
    total_deleted = 0

    for db_name, backups in backups_by_db.items():
        # Trier par date de modification (plus récent en premier)
        backups_sorted = sorted(
            backups,
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        # Garder seulement retention_count
        to_delete = backups_sorted[retention_count:]

        for backup_file in to_delete:
            try:
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                backup_file.unlink()
                logger.info(f"🗑️  Supprimé: {backup_file.name} ({size_mb:.2f} MB)")
                total_deleted += 1
            except Exception as e:
                logger.error(f"❌ Erreur suppression {backup_file.name}: {e}")

    if total_deleted > 0:
        logger.info(f"✅ {total_deleted} ancien(s) backup(s) supprimé(s)")
    else:
        logger.info("ℹ️  Aucun ancien backup à supprimer")


def get_backup_stats(data_dir: str = "data", backup_subdir: str = "backups"):
    """
    Affiche des statistiques sur les backups.
    """
    backup_path = Path(data_dir) / backup_subdir

    if not backup_path.exists():
        logger.info("ℹ️  Aucun backup existant")
        return

    backups = list(backup_path.glob("*.db"))

    if not backups:
        logger.info("ℹ️  Répertoire backup vide")
        return

    total_size = sum(f.stat().st_size for f in backups)
    total_size_mb = total_size / (1024 * 1024)

    logger.info(f"📊 Statistiques backups:")
    logger.info(f"   - Nombre: {len(backups)}")
    logger.info(f"   - Taille totale: {total_size_mb:.2f} MB")
    logger.info(f"   - Répertoire: {backup_path}")


def restore_latest_backup(db_name: str, data_dir: str = "data", backup_subdir: str = "backups"):
    """
    Restaure le backup le plus récent d'une DB.

    Args:
        db_name: Nom de la DB (sans extension)
        data_dir: Répertoire data
        backup_subdir: Sous-répertoire backups
    """
    data_path = Path(data_dir)
    backup_path = data_path / backup_subdir

    # Trouver tous les backups de cette DB
    pattern = f"{db_name}_*.db"
    backups = sorted(
        backup_path.glob(pattern),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    if not backups:
        logger.error(f"❌ Aucun backup trouvé pour {db_name}")
        return False

    latest_backup = backups[0]
    target_file = data_path / f"{db_name}.db"

    # Sauvegarder DB actuelle si elle existe
    if target_file.exists():
        temp_backup = data_path / f"{db_name}_before_restore.db"
        shutil.copy2(target_file, temp_backup)
        logger.info(f"💾 DB actuelle sauvegardée: {temp_backup.name}")

    # Restaurer le backup
    try:
        shutil.copy2(latest_backup, target_file)
        size_mb = latest_backup.stat().st_size / (1024 * 1024)
        logger.info(f"✅ DB restaurée depuis: {latest_backup.name} ({size_mb:.2f} MB)")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur restauration: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backup/restore des bases SQLite")
    parser.add_argument(
        "--action",
        choices=["backup", "stats", "restore"],
        default="backup",
        help="Action à effectuer"
    )
    parser.add_argument(
        "--db-name",
        help="Nom de la DB pour restore (sans extension)"
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=30,
        help="Nombre de backups à garder (défaut: 30)"
    )

    args = parser.parse_args()

    if args.action == "backup":
        logger.info("🚀 Démarrage backup automatique")
        backup_databases(retention_count=args.retention)
        get_backup_stats()
        logger.info("✅ Backup terminé")

    elif args.action == "stats":
        get_backup_stats()

    elif args.action == "restore":
        if not args.db_name:
            logger.error("❌ --db-name requis pour restore")
            exit(1)
        restore_latest_backup(args.db_name)
