"""
Tests unitaires pour le client Asana.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.asana_client import AsanaClient, AsanaClientError


class TestAsanaClient:

    def test_init_without_token_raises_error(self):
        """Vérifie qu'une erreur est levée sans token."""
        with pytest.raises(AsanaClientError) as exc_info:
            AsanaClient('')

        assert 'Token Asana requis' in str(exc_info.value)

    def test_init_with_none_token_raises_error(self):
        """Vérifie qu'une erreur est levée avec token None."""
        with pytest.raises(AsanaClientError) as exc_info:
            AsanaClient(None)

        assert 'Token Asana requis' in str(exc_info.value)

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_init_with_valid_token(self, mock_users, mock_projects, mock_tasks, mock_api_client, mock_config):
        """Vérifie l'initialisation avec un token valide."""
        client = AsanaClient('valid_token')

        mock_config.assert_called_once()
        mock_api_client.assert_called_once()
        assert client.tasks_api is not None
        assert client.projects_api is not None
        assert client.users_api is not None

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_test_connection_success(self, mock_users_class, mock_projects, mock_tasks, mock_api_client, mock_config):
        """Vérifie le test de connexion réussi."""
        mock_users = Mock()
        mock_users.get_user.return_value = {
            'gid': '12345',
            'name': 'Test User',
            'email': 'test@example.com'
        }
        mock_users_class.return_value = mock_users

        client = AsanaClient('valid_token')
        result = client.test_connection()

        assert result['gid'] == '12345'
        assert result['name'] == 'Test User'
        assert result['email'] == 'test@example.com'

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_test_connection_failure(self, mock_users_class, mock_projects, mock_tasks, mock_api_client, mock_config):
        """Vérifie le test de connexion échoué."""
        mock_users = Mock()
        mock_users.get_user.side_effect = Exception('API Error')
        mock_users_class.return_value = mock_users

        client = AsanaClient('invalid_token')

        with pytest.raises(AsanaClientError) as exc_info:
            client.test_connection()

        assert 'Échec connexion Asana' in str(exc_info.value)

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_get_project_tasks_without_gid_raises_error(self, mock_users, mock_projects, mock_tasks, mock_api_client, mock_config):
        """Vérifie qu'une erreur est levée sans project GID."""
        client = AsanaClient('valid_token')

        with pytest.raises(AsanaClientError) as exc_info:
            client.get_project_tasks('')

        assert 'Project GID requis' in str(exc_info.value)

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_get_project_tasks_success(self, mock_users, mock_projects, mock_tasks_class, mock_api_client, mock_config):
        """Vérifie la récupération des tasks."""
        # Mock des tasks
        mock_task1 = Mock()
        mock_task1.to_dict.return_value = {'gid': '1', 'name': 'Task 1', 'completed': False}
        mock_task2 = Mock()
        mock_task2.to_dict.return_value = {'gid': '2', 'name': 'Task 2', 'completed': False}
        mock_task3 = Mock()
        mock_task3.to_dict.return_value = {'gid': '3', 'name': 'Task 3', 'completed': True}

        mock_result = Mock()
        mock_result.data = [mock_task1, mock_task2, mock_task3]
        mock_result.next_page = None

        mock_tasks = Mock()
        mock_tasks.get_tasks_for_project.return_value = mock_result
        mock_tasks_class.return_value = mock_tasks

        client = AsanaClient('valid_token')
        tasks = client.get_project_tasks('project_123', include_completed=False)

        # Devrait exclure les tasks complétées
        assert len(tasks) == 2

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_get_project_tasks_include_completed(self, mock_users, mock_projects, mock_tasks_class, mock_api_client, mock_config):
        """Vérifie l'inclusion des tasks complétées."""
        mock_task1 = Mock()
        mock_task1.to_dict.return_value = {'gid': '1', 'name': 'Task 1', 'completed': False}
        mock_task2 = Mock()
        mock_task2.to_dict.return_value = {'gid': '2', 'name': 'Task 2', 'completed': True}

        mock_result = Mock()
        mock_result.data = [mock_task1, mock_task2]
        mock_result.next_page = None

        mock_tasks = Mock()
        mock_tasks.get_tasks_for_project.return_value = mock_result
        mock_tasks_class.return_value = mock_tasks

        client = AsanaClient('valid_token')
        tasks = client.get_project_tasks('project_123', include_completed=True)

        assert len(tasks) == 2

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_get_custom_field_gids_success(self, mock_users, mock_projects_class, mock_tasks, mock_api_client, mock_config):
        """Vérifie la récupération des GIDs des custom fields."""
        mock_project = Mock()
        mock_project.to_dict.return_value = {
            'custom_field_settings': [
                {'custom_field': {'gid': 'cf_1', 'name': 'Client'}},
                {'custom_field': {'gid': 'cf_2', 'name': 'Budget'}},
            ]
        }

        mock_projects = Mock()
        mock_projects.get_project.return_value = mock_project
        mock_projects_class.return_value = mock_projects

        client = AsanaClient('valid_token')
        fields = client.get_custom_field_gids('project_123')

        assert fields['Client'] == 'cf_1'
        assert fields['Budget'] == 'cf_2'

    @patch('core.asana_client.asana.Configuration')
    @patch('core.asana_client.asana.ApiClient')
    @patch('core.asana_client.asana.TasksApi')
    @patch('core.asana_client.asana.ProjectsApi')
    @patch('core.asana_client.asana.UsersApi')
    def test_get_project_info_success(self, mock_users, mock_projects_class, mock_tasks, mock_api_client, mock_config):
        """Vérifie la récupération des infos projet."""
        mock_project = Mock()
        mock_project.to_dict.return_value = {
            'gid': 'project_123',
            'name': 'Sales Pipeline',
            'notes': 'Pipeline des ventes',
            'owner': {'name': 'Manager'}
        }

        mock_projects = Mock()
        mock_projects.get_project.return_value = mock_project
        mock_projects_class.return_value = mock_projects

        client = AsanaClient('valid_token')
        info = client.get_project_info('project_123')

        assert info['gid'] == 'project_123'
        assert info['name'] == 'Sales Pipeline'
        assert info['owner'] == 'Manager'
