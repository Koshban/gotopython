from influxdb import InfluxDBClient
from prometheus_client import start_http_server, Gauge
import requests
import json
import time
import exporterconfig
import SLOqueries

influxdbconn = (exporterconfig.host, exporterconfig.port, exporterconfig.username, exporterconfig.password, exporterconfig.database )

# Connect to InfluxDB
"""
Connects to the InfluxDB database.

Args:
    influxdbconn (str): The connection string for the InfluxDB.

Returns:
    None
"""
client = InfluxDBClient(influxdbconn)

# Create Prometheus metrics
metrics = {}
for query_name in SLOqueries.queries:
    metrics[query_name] = Gauge(query_name, "Metric generated from InfluxDB query: " + query_name)

# Function to execute a query and update the corresponding Prometheus metric
def execute_query(query_name, query, metric):
    """
    Execute a query on InfluxDB and update the corresponding Prometheus metric.

    Args:
        query_name (str): The name of the query.
        query (str): The InfluxDB query to be executed.
        metric (Gauge): The Prometheus metric object to be updated.

    Returns:
        None
    """
    result = client.query(query)
    data_points = list(result.get_points())
    if data_points:
        value = data_points[0].get(query_name,"UNKN")  # Change to the appropriate field for your query
        metric.set(value)

# Function to push metrics to Prometheus Pushgateway
def push_to_prometheus(metrics):
    """
    Push metrics to the Prometheus Pushgateway.

    Args:
        metrics (list): List of Prometheus metrics to be pushed.

    Returns:
        None
    """
    data = '\n'.join(metrics)
    headers = {'Content-Type': 'text/plain'}
    response = requests.post(exporterconfig.prometheus_pushgateway_url, headers=headers, data=data)
    if response.status_code == 202:
        print('Metrics successfully pushed to Prometheus Pushgateway')
    else:
        print(f'Failed to push metrics to Prometheus Pushgateway. Status code: {response.status_code}')

# Loop to execute queries at the specified frequencies
def execute_queries():
    """
    Execute queries at the specified frequencies and push the metrics to Prometheus.

    Args:
        None

    Returns:
        None
    """
    metrics = []
    current_time = time.time()
    for query_name, query_info in SLOqueries.queries.items():
        query = query_info['query']
        frequency = query_info['frequency']
        last_execution_time = query_info.get('last_execution_time', 0)
        if current_time - last_execution_time >= frequency:
            metric = metrics[query_name]
            execute_query(query_name, query, metric)
            query_info['last_execution_time'] = current_time
            metrics.append(metrics[query_name])

    if metrics:
        push_to_prometheus(metrics)

# Start the Prometheus HTTP server
start_http_server(exporterconfig.prometheusport)
"""
Starts the Prometheus HTTP server.

Args:
    exporterconfig.prometheusport (int): The port number for the Prometheus HTTP server.

Returns:
    None
"""
# Loop to execute queries periodically
if __name__ == "__main__":
    while True:
        execute_queries()
        time.sleep(15)  # Sleep for 15 second