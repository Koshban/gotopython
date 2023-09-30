import gzip
import json
import prometheus_client.core
import string
import threading
import time
import prometheus_client
from prometheus_client import Gauge, Counter, REGISTRY, CollectorRegistry, push_to_gateway, Summary
from prometheus_client.utils import INF
from prometheus_client.core import CollectorRegistry
import logging
import kingpin
import json
import os
import fmt
import http
# In the Python translation, we use the prometheus_client library 
# to define metrics. We import the required classes Gauge, Counter, 
# and REGISTRY from the library. The variable assignments and metric 
# definitions remain the same as in the Go code.
MAX_UDP_PAYLOAD = 64 * 1024

listenAddress = ":9122"
metricsPath = "/metrics"
exporterMetricsPath = "/metrics/exporter"
sampleExpiry = 5 * 60
bindAddress = ":9122"
exportTimestamp = False

lastPush = Gauge(
    "influxdb_last_push_timestamp_seconds",
    "Unix timestamp of the last received influxdb metrics push in seconds."
)
udpParseErrors = Counter(
    "influxdb_udp_parse_errors_total",
    "Current total udp parse errors."
)
influxDbRegistry = REGISTRY
# In Python, we define classes InfluxDBSample, InfluxV2Health, and ErrorResponse to represent the corresponding Go structs. Each class has an __init__ method that initializes the class attributes to their default values.
# Please note that the Python translation assumes you have the time module imported for working with timestamps. Feel free to modify the class attributes and add additional methods as per your specific requirements.

class InfluxDBSample:
    def __init__(self):
        self.ID = ""
        self.Name = ""
        self.Labels = {}
        self.Value = 0.0
        self.Timestamp = time.time()

class InfluxV2Health:
    def __init__(self):
        self.Checks = []
        self.Commit = ""
        self.Message = ""
        self.Name = ""
        self.Status = ""
        self.Version = ""

class ErrorResponse:
    def __init__(self):
        self.Error = ""

class InfluxDBCollector:
    def __init__(self, logger):
        self.samples = {}
        self.mu = threading.Lock()
        self.ch = []
        self.logger = logger
        self.conn = None

    @classmethod
    def new_influxdb_collector(cls, logger):
        c = cls(logger)
        threading.Thread(target=c.process_samples).start()
        return c

    def influxdb_post(self, w, r):
        lastPush.set(float(time.time()))

        buf = []
        ce = r.headers.get("Content-Encoding")
        if ce == "gzip":
            gunzip = gzip.GzipFile(fileobj=r.body)
            buf = gunzip.read()
        else:
            buf = r.body

        precision = "ns"
        if "precision" in r.form:
            precision = r.form.get("precision")

        try:
            points = models.parse_points_with_precision(buf, time.time(), precision)
        except Exception as e:
            json_error_response(w, f"error parsing request: {e}", 400)
            return

        self.parse_points_to_sample(points)

        w.status = 204
        w.send_response()

    def parse_points_to_sample(self, points):
        for s in points:
            fields = s.fields()
            for field, v in fields.items():
                value = None
                if isinstance(v, float):
                    value = v
                elif isinstance(v, int):
                    value = float(v)
                elif isinstance(v, bool):
                    value = 1 if v else 0
                else:
                    continue

                name = s.name if field == "value" else s.name + "_" + field
                name = replace_invalid_chars(name)

                sample = influxDBSample(
                    name=name,
                    timestamp=s.time,
                    value=value,
                    labels={},
                )

                for tag in s.tags:
                    key = tag.key
                    value = tag.value
                    if key == "__name__":
                        continue
                    key = replace_invalid_chars(key)
                    sample.labels[key] = value

                label_names = sorted(sample.labels)
                parts = [name] + sum([[l, sample.labels[l]] for l in label_names], [])
                sample.id = ".".join(parts)

                self.ch.put(sample)

    def process_samples(self):
        ticker = threading.Event()
        while True:
            if ticker.wait(60):
                age_limit = time.time() - sampleExpiry.total_seconds()
                with self.mu:
                    self.samples = {k: v for k, v in self.samples.items() if v.timestamp >= age_limit}

    def collect(self):
        yield lastPush

        with self.mu:
            samples = list(self.samples.values())

        age_limit = time.time() - sampleExpiry.total_seconds()
        for sample in samples:
            if sample.timestamp < age_limit:
                continue

            metric = prometheus_client.core.Metric(
                sample.name,
                "InfluxDB Metric",
                [],
                sample.labels,
                prometheus_client.core.UntypedMetricFamily,
                sample.value,
            )

            if exportTimestamp:
                metric = prometheus_client.core.Metric(sample.timestamp, metric)

            yield metric

    def describe(self):
        yield lastPush

def replace_invalid_chars(s):
    for i, char in enumerate(s):
        char_int = ord(char)
        if not (97 <= char_int <= 122 or 65 <= char_int <= 90 or 48 <= char_int <= 57 or char_int == 95):
            s = s[:i] + "_" + s[i+1:]

    if 48 <= ord(s[0]) <= 57:
        s = "_" + s

    return s

def json_error_response(w, err, code):
    w.headers["Content-Type"] = "application/json; charset=utf-8"
    w.headers["X-Content-Type-Options"] = "nosniff"
    w.status = code
    w.write(json.dumps({"Error": err}))

class influxDBSample:
    def __init__(self, name, timestamp, value, labels):
        self.name = name
        self.timestamp = timestamp
        self.value = value
        self.labels = labels
        self.id = ""

def init():
    influxDbRegistry = CollectorRegistry()
    influxDbRegistry.register(prometheus_client.Collector(version.NewCollector("influxdb_exporter")))
    influxDbRegistry.register(udpParseErrors)
    # influxDbRegistry.MustRegister(version.NewCollector("influxdb_exporter"))
    # influxDbRegistry.MustRegister(udpParseErrors)

def main():
    promlogConfig = promlog.Config()
    kingpin.CommandLine().add_flags(promlogConfig)
    kingpin.HelpFlag().short('h')
    kingpin.Parse()

    logger = promlog.New(promlogConfig)
    logger.info("msg", "Starting influxdb_exporter", "version", version.Info())
    logger.info("msg", "Build context", "context", version.BuildContext())

    c = InfluxDBCollector.new_influxdb_collector(logger)
    influxDbRegistry.register(c)

    addr = net.ResolveUDPAddr("udp", bindAddress)
    try:
        conn = net.ListenUDP("udp", addr)
    except Exception as err:
        fmt.Printf("Failed to set up UDP listener at address %s: %s", addr, err)
        os.Exit(1)

    c.conn = conn
    c.serveUdp()

    http.HandleFunc("/write", c.influxdb_post)
    http.HandleFunc("/api/v2/write", c.influxdb_post)

    def query_handler(w, r):
        w.write('{"results": []}')
    http.HandleFunc("/query", query_handler)

    def api_query_handler(w, r):
        w.write('')
    http.HandleFunc("/api/v2/query", api_query_handler)

    def ping_handler(w, r):
        verbose = r.URL.Query().Get("verbose")

        if verbose != "" and verbose != "0" and verbose != "false":
            b, _ := json.Marshal(map[string]string{"version": version.Version})
            w.Write(b)
        else:
            w.Header().Set("X-Influxdb-Version", version.Version)
            w.WriteHeader(http.StatusNoContent)
    http.HandleFunc("/ping", ping_handler)

    def health_handler(w, r):
        health = {
            "Checks": [],
            "Version": version.Version,
            "Status": "pass",
            "Commit": version.Revision
        }
        w.WriteHeader(http.StatusOK)
        json.NewEncoder(w).Encode(health)
    http.HandleFunc("/health", health_handler)

    http.Handle(metricsPath, promhttp.HandlerFor(influxDbRegistry, promhttp.HandlerOpts()))
    http.Handle(exporterMetricsPath, promhttp.Handler())

    def default_handler(w, r):
        w.Write([]byte('<html>\n<head><title>InfluxDB Exporter</title></head>\n<body>\n<h1>InfluxDB Exporter</h1>\n<p><a href="' + metricsPath + '">Metrics</a></p>\n<p><a href="' + exporterMetricsPath + '">Exporter Metrics</a></p>\n</body>\n</html>'))
    http.HandleFunc("/", default_handler)

    try:
        http.ListenAndServe(listenAddress, None)
    except Exception as err:
        logger.error("msg", "Error starting HTTP server", "err", err)
        os.Exit(1)
if __name__ == "__main__":
    main()