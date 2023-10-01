from influxdb import InfluxDBClient
import time
import json

# Configure InfluxDB connection
host = 'localhost'
port = 8086
username = 'your_username'
password = 'your_password'
database = 'your_database'

# Configure query and execution frequency
query = "SELECT percentile(\"value\", 95) AS \"95th_percentile\" FROM measurements.gilgo"
execution_frequency = 900  # 900 seconds = 15 minutes

# Connect to InfluxDB
client = InfluxDBClient(host, port, username, password, database)

# Function to execute the query and process the result
def execute_query():
    result = client.query(query)
    # Process the result as per your requirements
    # For example, extract the data points and create a JSON object
    data_points = list(result.get_points())
    json_output = json.dumps(data_points)
    print(json_output)

# Loop to execute the query at the specified frequency
while True:
    execute_query()
    time.sleep(execution_frequency)