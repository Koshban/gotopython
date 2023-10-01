import argparse
import datetime
from prometheus_client import Gauge, Counter, REGISTRY, CollectorRegistry, push_to_gateway, Summary
import gzip
import io
import doqu
import sync
import time
import prometheus_client as prometheus
import json
import http
import kingpin
import os

MAX_UDP_PAYLOAD = 64 * 1024

listenAddress = argparse.ArgumentParser().add_argument("--web.listen-address", help="Address on which to expose metrics and web interface.", default=":9122").parse_args().web_listen_address
metricsPath = argparse.ArgumentParser().add_argument("--web.telemetry-path", help="Path under which to expose Prometheus metrics.", default="/metrics").parse_args().web_telemetry_path
exporterMetricsPath = argparse.ArgumentParser().add_argument("--web.exporter-telemetry-path", help="Path under which to expose exporter metrics.", default="/metrics/exporter").parse_args().web_exporter_telemetry_path
sampleExpiry = argparse.ArgumentParser().add_argument("--influxdb.sample-expiry", help="How long a sample is valid for.", default="5m").parse_args().influxdb_sample_expiry
bindAddress = argparse.ArgumentParser().add_argument("--udp.bind-address", help="Address on which to listen for udp packets.", default=":9122").parse_args().udp_bind_address
exportTimestamp = argparse.ArgumentParser().add_argument("--timestamps", help="Export timestamps of points.", default="false").parse_args().timestamps

lastPush = Gauge("influxdb_last_push_timestamp_seconds", "Unix timestamp of the last received influxdb metrics push in seconds.")
udpParseErrors = Counter("influxdb_udp_parse_errors_total", "Current total udp parse errors.")
influxDbRegistry = REGISTRY()

class influxDBSample:
    def __init__(self):
        self.ID = ""
        self.Name = ""
        self.Labels = {}
        self.Value = 0.0
        self.Timestamp = datetime.datetime.now()

class InfluxV2Health:
    def __init__(self):
        self.Checks = []
        self.Commit = ""
        self.Message = ""
        self.Name = ""
        self.Status = ""
        self.Version = ""

class errorResponse:
    def __init__(self):
        self.Error = ""

class influxDBCollector:
    def __init__(self, logger):
        self.samples = {}
        self.mu = sync.Mutex()
        self.ch = []
        self.logger = logger
        self.conn = net.UDPConn()

    def newInfluxDBCollector(logger):
        c = influxDBCollector(logger)
        c.ch = []
        c.samples = {}
        return c

    def influxDBPost(self, w, r):
        lastPush = time.Now().UnixNano() / 1e9
        buf = []
        ce = r.Header.Get("Content-Encoding")
        if ce == "gzip":
            bufPointer = buf
            gunzip, err = gzip.NewReader(r.Body)
            if err != nil:
                JSONErrorResponse(w, "error reading compressed body: {}".format(err), 500)
                return
            bufPointer, err = io.ReadAll(gunzip)
            if err != nil:
                JSONErrorResponse(w, "error decompressing data: {}".format(err), 500)
                return
        else:
            bufPointer = buf
            err = None
            bufPointer, err = io.ReadAll(r.Body)
            if err != nil:
                JSONErrorResponse(w, "error reading body: {}".format(err), 500)
                return
        precision = "ns"
        if r.FormValue("precision") != "":
            precision = r.FormValue("precision")
        points, err = models.ParsePointsWithPrecision(buf, time.Now().UTC(), precision)
        if err != nil:
            JSONErrorResponse(w, "error parsing request: {}".format(err), 400)
            return
        self.parsePointsToSample(points)
        http.Error(w, "", http.StatusNoContent)

    def parsePointsToSample(self, points):
        for s in points:
            fields, err = s.Fields()
            if err != nil:
                level.Error(self.logger).Log("msg", "error getting fields from point", "err", err)
                continue
            for field, v in fields.items():
                value = 0.0
                if isinstance(v, float):
                    value = v
                elif isinstance(v, int):
                    value = float(v)
                elif isinstance(v, bool):
                    if v:
                        value = 1
                    else:
                        value = 0
                else:
                    continue
                name = ""
                if field == "value":
                    name = str(s.Name())
                else:
                    name = str(s.Name()) + "_" + field
                ReplaceInvalidChars(name)
                sample = influxDBSample()
                sample.Name = name
                sample.Timestamp = s.Time()
                sample.Value = value
                sample.Labels = {}
                for v in s.Tags():
                    key = str(v.Key)
                    if key == "__name__":
                        continue
                    ReplaceInvalidChars(key)
                    sample.Labels[key] = str(v.Value)
                labelnames = []
                for k in sample.Labels.keys():
                    labelnames.append(k)
                labelnames.sort()
                parts = []
                parts.append(name)
                for l in labelnames:
                    parts.append(l)
                    parts.append(sample.Labels[l])
                sample.ID = ".".join(parts)
                self.ch.append(sample)


class influxDBCollector:
    def __init__(self):
        self.samples = {}
        self.mu = threading.Lock()
        self.ch = None

    def processSamples(self):
        ticker = time.minute
        while True:
            s = self.ch.get()
            self.mu.acquire()
            self.samples[s.ID] = s
            self.mu.release()
            if ticker:
                ageLimit = time.now() - sampleExpiry
                self.mu.acquire()
                for k, sample in self.samples.items():
                    if ageLimit.after(sample.Timestamp):
                        del self.samples[k]
                self.mu.release()

    def Collect(self, ch):
        ch.put(lastPush)
        self.mu.acquire()
        samples = []
        for sample in self.samples.values():
            samples.append(sample)
        self.mu.release()
        ageLimit = time.now() - sampleExpiry
        for sample in samples:
            if ageLimit.after(sample.Timestamp):
                continue
            metric = prometheus.Metric(
                prometheus.Desc(sample.Name, "InfluxDB Metric", [], sample.Labels),
                prometheus.UntypedValue,
                sample.Value,
            )
            if exportTimestamp:
                metric = prometheus.MetricWithTimestamp(sample.Timestamp, metric)
            ch.put(metric)

    def Describe(self, ch):
        ch.put(lastPush.Desc())

def ReplaceInvalidChars(in_):
    in_ = list(in_)
    for charIndex, char in enumerate(in_):
        charInt = ord(char)
        if not ((charInt >= 97 and charInt <= 122) or 
                (charInt >= 65 and charInt <= 90) or 
                (charInt >= 48 and charInt <= 57) or 
                charInt == 95):
            in_[charIndex] = "_"
    if ord(in_[0]) >= 48 and ord(in_[0]) <= 57:
        in_.insert(0, "_")
    in_ = "".join(in_)

def JSONErrorResponse(w, err, code):
    w.headers["Content-Type"] = "application/json; charset=utf-8"
    w.headers["X-Content-Type-Options"] = "nosniff"
    w.status = code
    json.dump({"Error": err}, w)

def init():
    """Initialize the InfluxDB exporter."""
    influxDbRegistry = CollectorRegistry()
    influxDbRegistry.register(prometheus_client.Collector(version.NewCollector("influxdb_exporter")))
    influxDbRegistry.register(udpParseErrors)
    # influxDbRegistry.MustRegister(version.NewCollector("influxdb_exporter"))
    # influxDbRegistry.MustRegister(udpParseErrors)

def main():
    """Main function for the InfluxDB exporter."""
    """ Entry point for the influxDB exporter. It initializes configurations, sets up logging, creates the influxDB collector. Registers it.
    sets up UDP listener, and configures various end points. Finally, it starts the HTTP server and logs any errors"""
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
        """Handler for the /query endpoint."""
        w.write('{"results": []}')
    http.HandleFunc("/query", query_handler)

    def api_query_handler(w, r):
        """Handler for the /api/v2/query endpoint."""
        w.write('')
    http.HandleFunc("/api/v2/query", api_query_handler)

    def ping_handler(w, r):
        """Handler for the /ping endpoint."""
        verbose = r.URL.Query().Get("verbose")

        if verbose != "" and verbose != "0" and verbose != "false":
            b, _ = json.Marshal(map[string]string{"version": version.Version})
            w.Write(b)
        else:
            w.Header().Set("X-Influxdb-Version", version.Version)
            w.WriteHeader(http.StatusNoContent)
    http.HandleFunc("/ping", ping_handler)

    def health_handler(w, r):
        """Handler for the /health endpoint."""
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
        """Default handler for other endpoints."""
        w.Write([]byte('<html>\n<head><title>InfluxDB Exporter</title></head>\n<body>\n<h1>InfluxDB Exporter</h1>\n<p><a href="' + metricsPath + '">Metrics</a></p>\n<p><a href="' + exporterMetricsPath + '">Exporter Metrics</a></p>\n</body>\n</html>'))
    http.HandleFunc("/", default_handler)

    try:
        http.ListenAndServe(listenAddress, None)
    except Exception as err:
        logger.error("msg", "Error starting HTTP server", "err", err)
        os.Exit(1)
if __name__ == "__main__":
    main()

