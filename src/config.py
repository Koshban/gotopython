MAX_UDP_PAYLOAD = 64 * 1024
listenAddress = ":18087"
metricsPath = "/metrics"
exporterMetricsPath = "/metrics/exporter"
sampleExpiry = 5 * 60
bindAddress = ":9122"
exportTimestamp = False
destinationAddress = ":9122"
prometheus_http_port = ":8000"
precision ="ns"
Influxdb_Version = "2.7"

# Bind the socket to a specific address and port
bind_address = ('localhost', bindAddress)