

# We use the prometheus_client library to define metrics.

MAX_UDP_PAYLOAD = 64 * 1024

listenAddress = ":9122"
metricsPath = "/metrics"
exporterMetricsPath = "/metrics/exporter"
sampleExpiry = 5 * 60
bindAddress = ":9122"
exportTimestamp = False

import gzip
import io
import json
import net
import os
import prometheus
import promhttp
import promlog
import sort
import strings
import sync
import time

MAX_UDP_PAYLOAD = 64 * 1024

listenAddress = ":9122"
metricsPath = "/metrics"
exporterMetricsPath = "/metrics/exporter"
sampleExpiry = 5 * 60
bindAddress = ":9122"
exportTimestamp = False

lastPush = prometheus.Gauge(
    "influxdb_last_push_timestamp_seconds",
    "Unix timestamp of the last received influxdb metrics push in seconds."
)
udpParseErrors = prometheus.Counter(
    "influxdb_udp_parse_errors_total",
    "Current total udp parse errors."
)
influxDbRegistry = prometheus.Registry()

class influxDBSample:
    def __init__(self):
        self.ID = ""
        self.Name = ""
        self.Labels = {}
        self.Value = 0.0
        self.Timestamp = time.Time()

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
        self.ch = chan(influxDBSample)
        self.logger = log.Logger()
        self.conn = net.UDPConn()

    def serveUdp(self):
        buf = bytearray(MAX_UDP_PAYLOAD)
        while True:
            n, _, err = self.conn.ReadFromUDP(buf)
            if err != None:
                level.Warn(self.logger).Log("msg", "Failed to read UDP message", "err", err)
                continue
            bufCopy = buf[:n].copy()
            precision = "ns"
            points, err = models.ParsePointsWithPrecision(bufCopy, time.Now().UTC(), precision)
            if err != None:
                level.Error(self.logger).Log("msg", "Error parsing udp packet", "err", err)
                udpParseErrors.Inc()
                continue
            self.parsePointsToSample(points)

    def newInfluxDBCollector(self, logger):
        c = influxDBCollector(logger)
        go c.processSamples()
        return c

    def influxDBPost(self, w, r):
        lastPush.Set(float64(time.Now().UnixNano()) / 1e9)
        buf = []
        ce = r.Header.Get("Content-Encoding")
        if ce == "gzip":
            gunzip, err = gzip.NewReader(r.Body)
            if err != None:
                JSONErrorResponse(w, "error reading compressed body: " + err, 500)
                return
            buf, err = io.ReadAll(gunzip)
            if err != None:
                JSONErrorResponse(w, "error decompressing data: " + err, 500)
                return
        else:
            buf, err = io.ReadAll(r.Body)
            if err != None:
                JSONErrorResponse(w, "error reading body: " + err, 500)
                return
        precision = "ns"
        if r.FormValue("precision") != "":
            precision = r.FormValue("precision")
        points, err = models.ParsePointsWithPrecision(buf, time.Now().UTC(), precision)
        if err != None:
            JSONErrorResponse(w, "error parsing request: " + err, 400)
            return
        self.parsePointsToSample(points)
        http.Error(w, "", http.StatusNoContent)

    def parsePointsToSample(self, points):
        for s in points:
            fields, err = s.Fields()
            if err != None:
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
                self.ch <- sample

    def processSamples(self):
        ticker = time.NewTicker(time.Minute).C
        while True:
            select {
            case s = <-self.ch:
                self.mu.Lock()
                self.samples[s.ID] = s
                self.mu.Unlock()
            case <-ticker:
                ageLimit = time.Now().Add(-sampleExpiry)
                self.mu.Lock()
                for k, sample in self.samples.items():
                    if ageLimit.After(sample.Timestamp):
                        del self.samples[k]
                self.mu.Unlock()

    def Collect(self, ch):
        ch <- lastPush
        self.mu.Lock()
        samples = []
        for _, sample in self.samples.items():
            samples.append(sample)
        self.mu.Unlock()
        ageLimit = time.Now().Add(-sampleExpiry)
        for sample in samples:
            if ageLimit.After(sample.Timestamp):
                continue
            metric = prometheus.MustNewConstMetric(
                prometheus.NewDesc(sample.Name, "InfluxDB Metric", [], sample.Labels),
                prometheus.UntypedValue,
                sample.Value
            )
            if exportTimestamp:
                metric = prometheus.NewMetricWithTimestamp(sample.Timestamp, metric)
            ch <- metric

    def Describe(self, ch):
        ch <- lastPush.Desc()

def ReplaceInvalidChars(in):
    for charIndex, char in enumerate(in):
        charInt = ord(char)
        if not ((charInt >= 97 and charInt <= 122) or 
                (charInt >= 65 and charInt <= 90) or 
                (charInt >= 48 and charInt <= 57) or 
                charInt == 95):
            in = in[:charIndex] + "_" + in[charIndex+1:]
    
    if ord(in[0]) >= 48 and ord(in[0]) <= 57:
        in = "_" + in

def JSONErrorResponse(w, err, code):
    w.Header().Set("Content-Type", "application/json; charset=utf-8")
    w.Header().Set("X-Content-Type-Options", "nosniff")
    w.WriteHeader(code)
    json.NewEncoder(w).Encode(errorResponse{
        Error: err,
    })

influxDbRegistry.MustRegister(version.NewCollector("influxdb_exporter"))
influxDbRegistry.MustRegister(udpParseErrors)

promlogConfig = promlog.Config()
kingpin.Parse()
logger = promlog.New(promlogConfig)
level.Info(logger).Log("msg", "Starting influxdb_exporter", "version", version.Info())
level.Info(logger).Log("msg", "Build context", "context", version.BuildContext())
c = influxDBCollector(logger)
influxDbRegistry.MustRegister(c)
addr, err = net.ResolveUDPAddr("udp", bindAddress)
if err != None:
    fmt.Printf("Failed to resolve UDP address %s: %s", bindAddress, err)
    os.Exit(1)
conn, err = net.ListenUDP("udp", addr)
if err != None:
    fmt.Printf("Failed to set up UDP listener at address %s: %s", addr, err)
    os.Exit(1)
c.conn = conn
go c.serveUdp()
http.HandleFunc("/write", c.influxDBPost)
http.HandleFunc("/api/v2/write", c.influxDBPost)

http.HandleFunc("/query", func(w, r) {
    fmt.Fprintf(w, `{"results": []}`)
})
http.HandleFunc("/api/v2/query", func(w, r) {
    fmt.Fprintf(w, ``)
})

http.HandleFunc("/ping", func(w, r) {
    verbose = r.URL.Query().Get("verbose")
    if verbose != "" and verbose != "0" and verbose != "false":
        b, _ = json.Marshal(map[string]string{"version": version.Version})
        w.Write(b)
    else:
        w.Header().Set("X-Influxdb-Version", version.Version)
        w.WriteHeader(http.StatusNoContent)
})
http.HandleFunc("/health", func(w, r) {
    health = InfluxV2Health()
    health.Checks = []
    health.Version = version.Version
    health.Status = "pass"
    health.Commit = version.Revision
    w.WriteHeader(http.StatusOK)
    err = json.NewEncoder(w).Encode(health)
    if err != None:
        level.Warn(logger).Log("failed to encode JSON for health endpoint", err)
})
http.Handle(metricsPath, promhttp.HandlerFor(influxDbRegistry, promhttp.HandlerOpts{}))
http.Handle(exporterMetricsPath, promhttp.Handler())
http.HandleFunc("/", func(w, r) {
    w.Write([]byte(`<html>
    <head><title>InfluxDB Exporter</title></head>
    <body>
    <h1>InfluxDB Exporter</h1>
    <p><a href="` + metricsPath + `">Metrics</a></p>
    <p><a href="` + exporterMetricsPath + `">Exporter Metrics</a></p>
    </body>
    </html>`))
})
if err := http.ListenAndServe(listenAddress, nil); err != None:
    level.Error(logger).Log("msg", "Error starting HTTP server", "err", err)
    os.Exit(1)
