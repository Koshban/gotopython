import pytest
import unittest
from unittest.mock import MagicMock, patch
from export_and_expose import execute_query, push_to_prometheus, execute_queries
import SLOqueries

# Pytest test case
@pytest.mark.parametrize("query_name, query, metric", [
    ("query1", "SELECT field1 FROM measurement1", MagicMock()),
    ("query2", "SELECT field2 FROM measurement2", MagicMock())
])
def test_execute_query(query_name, query, metric):
    """
    Test case for execute_query function.

    Args:
        query_name (str): The name of the query.
        query (str): The InfluxDB query to be executed.
        metric (MagicMock): The mock object for Prometheus metric.

    Returns:
        None
    """
    execute_query(query_name, query, metric)
    metric.set.assert_called_once()

# Unittest test case

class TestPushToPrometheus(unittest.TestCase):
    @patch('requests.post')
    def test_push_to_prometheus_success(self, mock_post):
        """
        Test case for push_to_prometheus function when metrics are successfully pushed.

        Args:
            mock_post (MagicMock): The mock object for requests.post.

        Returns:
            None
        """
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        metrics = ['metric1', 'metric2']
        push_to_prometheus(metrics)

        mock_post.assert_called_once_with(
            'prometheus_pushgateway_url',
            headers={'Content-Type': 'text/plain'},
            data='metric1\nmetric2'
        )

    @patch('requests.post')
    def test_push_to_prometheus_failure(self, mock_post):
        """
        Test case for push_to_prometheus function when pushing metrics fails.

        Args:
            mock_post (MagicMock): The mock object for requests.post.

        Returns:
            None
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        metrics = ['metric1', 'metric2']
        push_to_prometheus(metrics)

        mock_post.assert_called_once_with(
            'prometheus_pushgateway_url',
            headers={'Content-Type': 'text/plain'},
            data='metric1\nmetric2'
        )

class TestExecuteQueries(unittest.TestCase):
    @patch('time.time')
    @patch('mymodule.execute_query')
    def test_execute_queries(self, mock_execute_query, mock_time):
        """
        Test case for execute_queries function.

        Args:
            mock_execute_query (MagicMock): The mock object for execute_query function.
            mock_time (MagicMock): The mock object for time.time.

        Returns:
            None
        """
        mock_time.return_value = 1000

        query1_metric = MagicMock()
        query2_metric = MagicMock()
        metrics = {'query1': query1_metric, 'query2': query2_metric}
        SLOqueries.queries = {
            'query1': {'query': 'SELECT field1 FROM measurement1', 'frequency': 10},
            'query2': {'query': 'SELECT field2 FROM measurement2', 'frequency': 5}
        }

        execute_queries()

        mock_execute_query.assert_called_with('query1', 'SELECT field1 FROM measurement1', query1_metric)
        mock_execute_query.assert_called_with('query2', 'SELECT field2 FROM measurement2', query2_metric)

if __name__ == '__main__':
    unittest.main()