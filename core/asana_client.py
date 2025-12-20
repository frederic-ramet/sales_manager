"""
Client API Asana pour récupérer les deals du pipeline.
Compatible avec asana SDK v5+
"""

import asana
from asana.rest import ApiException
from typing import Dict, List, Optional
import time
import logging

logger = logging.getLogger(__name__)


class AsanaClientError(Exception):
    """Erreur spécifique au client Asana."""
    pass


class AsanaClient:
    """Client API Asana pour récupérer les deals du pipeline."""

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # secondes

    # Champs à récupérer pour chaque task
    OPT_FIELDS = [
        'name',
        'completed',
        'custom_fields',
        'custom_fields.name',
        'custom_fields.display_value',
        'custom_fields.number_value',
        'custom_fields.text_value',
        'custom_fields.date_value',
        'custom_fields.enum_value',
        'custom_fields.type',
        'assignee.name',
        'due_on',
        'memberships.section.name',
        'created_at',
        'modified_at',
    ]

    def __init__(self, access_token: str):
        """
        Initialise le client Asana.

        Args:
            access_token: Personal Access Token Asana
        """
        if not access_token:
            raise AsanaClientError("Token Asana requis")

        # Configuration du SDK v5
        configuration = asana.Configuration()
        configuration.access_token = access_token

        self.api_client = asana.ApiClient(configuration)
        self.tasks_api = asana.TasksApi(self.api_client)
        self.projects_api = asana.ProjectsApi(self.api_client)
        self.users_api = asana.UsersApi(self.api_client)

    def test_connection(self) -> Dict:
        """
        Teste la connexion à l'API Asana.

        Returns:
            Informations sur l'utilisateur connecté
        """
        try:
            opts = {'opt_fields': 'name,email'}
            me = self.users_api.get_user('me', opts)
            data = me.to_dict() if hasattr(me, 'to_dict') else me
            return {
                'gid': data.get('gid'),
                'name': data.get('name'),
                'email': data.get('email', 'N/A')
            }
        except ApiException as e:
            raise AsanaClientError(f"Échec connexion Asana: {e.reason}")
        except Exception as e:
            raise AsanaClientError(f"Échec connexion Asana: {e}")

    def get_project_tasks(self, project_gid: str, include_completed: bool = False) -> List[Dict]:
        """
        Récupère toutes les tasks d'un projet avec leurs custom fields.

        Args:
            project_gid: GID du projet Asana
            include_completed: Inclure les tasks terminées

        Returns:
            Liste de dicts avec les infos des tasks
        """
        if not project_gid:
            raise AsanaClientError("Project GID requis")

        tasks = []
        retries = 0
        offset = None

        while retries < self.MAX_RETRIES:
            try:
                # Récupération avec pagination
                opts = {
                    'opt_fields': ','.join(self.OPT_FIELDS),
                    'limit': 100,
                }
                if offset:
                    opts['offset'] = offset

                result = self.tasks_api.get_tasks_for_project(project_gid, opts)

                for task in result.data:
                    task_dict = task.to_dict() if hasattr(task, 'to_dict') else task
                    # Filtrer les tasks complétées si demandé
                    if not include_completed and task_dict.get('completed', False):
                        continue
                    tasks.append(task_dict)

                # Vérifier s'il y a plus de résultats
                if hasattr(result, 'next_page') and result.next_page:
                    offset = result.next_page.get('offset')
                else:
                    break

            except ApiException as e:
                if e.status == 429:
                    # Rate limit - attendre et réessayer
                    wait_time = self.RETRY_DELAY * (retries + 1)
                    logger.warning(f"Rate limit atteint, attente {wait_time}s...")
                    time.sleep(wait_time)
                    retries += 1
                    continue
                elif e.status == 404:
                    raise AsanaClientError(f"Projet {project_gid} introuvable")
                elif e.status == 403:
                    raise AsanaClientError(f"Accès refusé au projet {project_gid}")
                else:
                    retries += 1
                    if retries >= self.MAX_RETRIES:
                        raise AsanaClientError(f"Erreur API Asana: {e.reason}")
                    time.sleep(self.RETRY_DELAY * retries)
                    continue

            except Exception as e:
                retries += 1
                if retries >= self.MAX_RETRIES:
                    raise AsanaClientError(f"Erreur API Asana après {retries} tentatives: {e}")
                time.sleep(self.RETRY_DELAY * retries)
                continue

            # Sort de la boucle si pas de pagination
            break

        logger.info(f"Récupéré {len(tasks)} tasks depuis Asana")
        return tasks

    def get_custom_field_gids(self, project_gid: str) -> Dict[str, str]:
        """
        Récupère les GIDs des custom fields du projet.
        Utile pour validation et debugging.

        Args:
            project_gid: GID du projet Asana

        Returns:
            Dict {nom_field: gid}
        """
        try:
            opts = {'opt_fields': 'custom_field_settings.custom_field.name'}
            project = self.projects_api.get_project(project_gid, opts)

            fields = {}
            project_dict = project.to_dict() if hasattr(project, 'to_dict') else project

            for setting in project_dict.get('custom_field_settings', []):
                cf = setting.get('custom_field', {})
                name = cf.get('name')
                gid = cf.get('gid')
                if name and gid:
                    fields[name] = gid

            return fields

        except ApiException as e:
            raise AsanaClientError(f"Erreur récupération custom fields: {e.reason}")
        except Exception as e:
            raise AsanaClientError(f"Erreur récupération custom fields: {e}")

    def get_project_info(self, project_gid: str) -> Dict:
        """
        Récupère les informations de base d'un projet.

        Args:
            project_gid: GID du projet Asana

        Returns:
            Dict avec name, gid, etc.
        """
        try:
            opts = {'opt_fields': 'name,notes,owner.name'}
            project = self.projects_api.get_project(project_gid, opts)
            project_dict = project.to_dict() if hasattr(project, 'to_dict') else project

            owner = project_dict.get('owner')
            owner_name = owner.get('name', 'N/A') if owner else 'N/A'

            return {
                'gid': project_dict.get('gid'),
                'name': project_dict.get('name'),
                'notes': project_dict.get('notes', ''),
                'owner': owner_name
            }
        except ApiException as e:
            raise AsanaClientError(f"Erreur récupération projet: {e.reason}")
        except Exception as e:
            raise AsanaClientError(f"Erreur récupération projet: {e}")
