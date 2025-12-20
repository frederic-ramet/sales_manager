"""
Scheduler pour synchronisation automatique Asana → Google Sheets.
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "scheduler_config.json"


class SchedulerConfig:
    """Configuration du scheduler, persistée en JSON."""

    def __init__(self):
        self.enabled: bool = False
        self.frequency: str = "daily"  # "daily" ou "weekly"
        self.time: str = "09:00"  # HH:MM
        self.last_run: Optional[str] = None
        self.last_status: Optional[str] = None
        self.next_run: Optional[str] = None
        self._load()

    def _load(self):
        """Charge la config depuis le fichier JSON."""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                    self.enabled = data.get('enabled', False)
                    self.frequency = data.get('frequency', 'daily')
                    self.time = data.get('time', '09:00')
                    self.last_run = data.get('last_run')
                    self.last_status = data.get('last_status')
                    self.next_run = data.get('next_run')
            except Exception as e:
                logger.warning(f"Erreur lecture config scheduler: {e}")

    def save(self):
        """Sauvegarde la config dans le fichier JSON."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump({
                'enabled': self.enabled,
                'frequency': self.frequency,
                'time': self.time,
                'last_run': self.last_run,
                'last_status': self.last_status,
                'next_run': self.next_run
            }, f, indent=2)

    def update(self, enabled: bool = None, frequency: str = None, time: str = None):
        """Met à jour la config et sauvegarde."""
        if enabled is not None:
            self.enabled = enabled
        if frequency is not None:
            self.frequency = frequency
        if time is not None:
            self.time = time
        self.save()


class SyncScheduler:
    """
    Scheduler pour exécuter la sync automatiquement.

    Usage:
        scheduler = SyncScheduler()
        scheduler.set_sync_function(my_sync_func)
        scheduler.start()
    """

    def __init__(self):
        self.config = SchedulerConfig()
        self._scheduler = BackgroundScheduler()
        self._sync_function: Optional[Callable] = None
        self._job_id = "sync_job"

    def set_sync_function(self, func: Callable):
        """
        Définit la fonction de sync à exécuter.

        Args:
            func: Fonction sans argument qui effectue la sync
        """
        self._sync_function = func

    def _execute_sync(self):
        """Exécute la sync et met à jour le statut."""
        if not self._sync_function:
            logger.error("Aucune fonction de sync définie")
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Exécution sync automatique: {timestamp}")

        try:
            self._sync_function()
            self.config.last_run = timestamp
            self.config.last_status = "success"
            logger.info("Sync automatique réussie")
        except Exception as e:
            self.config.last_run = timestamp
            self.config.last_status = f"error: {str(e)}"
            logger.error(f"Erreur sync automatique: {e}")

        # Mettre à jour next_run
        self._update_next_run()
        self.config.save()

    def _update_next_run(self):
        """Met à jour la prochaine exécution prévue."""
        job = self._scheduler.get_job(self._job_id)
        if job and job.next_run_time:
            self.config.next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            self.config.next_run = None

    def _get_trigger(self) -> CronTrigger:
        """Crée le trigger cron selon la config."""
        hour, minute = self.config.time.split(':')

        if self.config.frequency == "weekly":
            # Tous les lundis
            return CronTrigger(day_of_week='mon', hour=int(hour), minute=int(minute))
        else:
            # Tous les jours
            return CronTrigger(hour=int(hour), minute=int(minute))

    def start(self):
        """Démarre le scheduler si activé."""
        if not self.config.enabled:
            logger.info("Scheduler désactivé, pas de démarrage")
            return

        if not self._sync_function:
            logger.warning("Aucune fonction de sync définie")
            return

        # Supprimer le job existant s'il y en a un
        if self._scheduler.get_job(self._job_id):
            self._scheduler.remove_job(self._job_id)

        # Ajouter le nouveau job
        trigger = self._get_trigger()
        self._scheduler.add_job(
            self._execute_sync,
            trigger=trigger,
            id=self._job_id,
            name="Sync Asana → Sheets"
        )

        # Démarrer le scheduler s'il n'est pas déjà actif
        if not self._scheduler.running:
            self._scheduler.start()

        self._update_next_run()
        self.config.save()
        logger.info(f"Scheduler démarré ({self.config.frequency} à {self.config.time})")

    def stop(self):
        """Arrête le scheduler."""
        if self._scheduler.get_job(self._job_id):
            self._scheduler.remove_job(self._job_id)

        self.config.next_run = None
        self.config.save()
        logger.info("Scheduler arrêté")

    def restart(self):
        """Redémarre le scheduler avec la nouvelle config."""
        self.stop()
        if self.config.enabled:
            self.start()

    def set_frequency(self, frequency: str):
        """
        Change la fréquence et redémarre si nécessaire.

        Args:
            frequency: "daily" ou "weekly"
        """
        if frequency not in ("daily", "weekly"):
            raise ValueError("Fréquence doit être 'daily' ou 'weekly'")

        self.config.update(frequency=frequency)
        if self.config.enabled:
            self.restart()

    def set_time(self, time: str):
        """
        Change l'heure d'exécution et redémarre si nécessaire.

        Args:
            time: Heure au format "HH:MM"
        """
        # Validation basique
        try:
            hour, minute = time.split(':')
            assert 0 <= int(hour) <= 23
            assert 0 <= int(minute) <= 59
        except:
            raise ValueError("Format d'heure invalide (attendu: HH:MM)")

        self.config.update(time=time)
        if self.config.enabled:
            self.restart()

    def enable(self):
        """Active le scheduler."""
        self.config.update(enabled=True)
        self.start()

    def disable(self):
        """Désactive le scheduler."""
        self.config.update(enabled=False)
        self.stop()

    def get_status(self) -> dict:
        """
        Retourne le statut actuel du scheduler.

        Returns:
            Dict avec enabled, frequency, time, last_run, last_status, next_run
        """
        return {
            'enabled': self.config.enabled,
            'frequency': self.config.frequency,
            'time': self.config.time,
            'last_run': self.config.last_run,
            'last_status': self.config.last_status,
            'next_run': self.config.next_run,
            'running': self._scheduler.running if hasattr(self._scheduler, 'running') else False
        }

    def shutdown(self):
        """Arrête complètement le scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
