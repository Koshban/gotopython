import os

# Set default values for the variables
host = os.environ.get('HOST', 'localhost')
port = int(os.environ.get('PORT', '18087'))
username = os.environ.get('USERNAME', 'your_username')
password = os.environ.get('PASSWORD', 'your_password')
database = os.environ.get('DATABASE', 'your_database')
prometheus_pushgateway_url = os.environ.get('PROMETHEUS_PUSHGATEWAY_URL', 'http://localhost:9091/metrics/job/my_job')
prometheusport = int(os.environ.get('PROMETHEUS_PORT', '8080'))

