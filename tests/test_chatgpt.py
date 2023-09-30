# Import the functions/classes you want to test
import time
from unittest import mock
import pytest
from unittest.mock import MagicMock, patch
from http import HTTPStatus
from influxdb_exporter_main import InfluxDBCollector, influxDBSample, replace_invalid_chars


@pytest.fixture
def influxdb_collector():
    logger_mock = MagicMock()
    return InfluxDBCollector.new_influxdb_collector(logger_mock)


def test_influxdb_post_success(influxdb_collector):
    # Mock the necessary objects for the test
    request_mock = MagicMock()
    request_mock.headers.get.return_value = None
    request_mock.body = b'{"metric_name": "value"}'
    response_mock = MagicMock()

    with patch.object(influxdb_collector, 'parse_points_to_sample') as mock_parse_points:
        # Call the function to be tested
        influxdb_collector.influxdb_post(response_mock, request_mock)
    
    # Assert that the necessary methods were called
    assert response_mock.status == HTTPStatus.NO_CONTENT
    assert response_mock.send_response.call_count == 1
    mock_parse_points.assert_called_once()


def test_influxdb_post_invalid_request(influxdb_collector):
    # Mock the necessary objects for the test
    request_mock = MagicMock()
    request_mock.headers.get.return_value = None
    request_mock.body = b'{"invalid_json"}'
    response_mock = MagicMock()

    with patch.object(influxdb_collector, 'json_error_response') as mock_error_response:
        # Call the function to be tested
        influxdb_collector.influxdb_post(response_mock, request_mock)

    # Assert that the necessary methods were called
    assert response_mock.status == HTTPStatus.BAD_REQUEST
    assert response_mock.write.call_count == 1
    mock_error_response.assert_called_once()


def test_parse_points_to_sample(influxdb_collector):
    # Mock the necessary objects for the test
    point_mock = MagicMock()
    point_mock.name = 'metric_name'
    point_mock.time = 1633085189.123
    point_mock.fields.return_value = {'value': 42}
    point_mock.tags = [{'key': 'tag_name', 'value': 'tag_value'}]

    influxdb_collector.ch = MagicMock()

    # Call the function to be tested
    influxdb_collector.parse_points_to_sample([point_mock])

    # Assert that the necessary methods were called
    assert influxdb_collector.ch.put.call_count == 1
    assert isinstance(influxdb_collector.ch.put.call_args[0][0], influxDBSample)


def test_replace_invalid_chars():
    assert replace_invalid_chars("metric_name") == "metric_name"
    assert replace_invalid_chars("metric_name_1") == "metric_name_1"
    assert replace_invalid_chars("metric name") == "metric_name"
    assert replace_invalid_chars("metric@name") == "metric_name"
    assert replace_invalid_chars("123metric_name") == "_123metric_name"
    assert replace_invalid_chars("metric_name_!") == "metric_name__"

# Dummy logger for testing
class MockLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

# Test the replace_invalid_chars function
def test_replace_invalid_chars():
    assert replace_invalid_chars("valid_name") == "valid_name"
    assert replace_invalid_chars("invalid name") == "invalid_name"
    assert replace_invalid_chars("123invalid") == "_123invalid"
    assert replace_invalid_chars("inva!lid") == "inva_lid"

# Test the InfluxDBCollector class
def test_influxdb_collector():
    logger = MockLogger()

    # Test new_influxdb_collector method
    collector = InfluxDBCollector.new_influxdb_collector(logger)
    assert isinstance(collector, InfluxDBCollector)

    # Test influxdb_post method with valid data
    request = mock.Mock()
    request.headers.get.return_value = None
    request.body = b'metric1,value=10 1633012345'
    collector.influxdb_post(mock.Mock(), request)
    assert len(collector.samples) == 1

    # Test influxdb_post method with invalid data
    request.body = b'invalid data'
    response = mock.Mock()
    collector.influxdb_post(response, request)
    assert response.status == 400

    # Test parse_points_to_sample method
    sample = InfluxDBSample()
    sample.name = 'metric1'
    sample.timestamp = time.time()
    sample.value = 10.0
    sample.labels = {}
    points = [sample]
    collector.parse_points_to_sample(points)
    assert len(collector.ch) == 1

    # Test process_samples method
    collector.samples = {'metric1': sample}
    collector.process_samples()
    assert len(collector.samples) == 1

    # Test collect method
    metrics = list(collector.collect())
    assert len(metrics) == 1

    # Test describe method
    descriptions = list(collector.describe())
    assert len(descriptions) == 1

# Run the tests
if __name__ == '__main__':
    pytest.main()