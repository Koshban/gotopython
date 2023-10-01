# Configure queries and execution frequencies

queries = {
    "95tile": {
        "query": "SELECT percentile(\"value\", 95) AS \"95th_percentile\" FROM measurements.gilgo",
        "frequency": 900  # 900 seconds = 15 minutes        
    },
    "average": {
        "query": "SELECT mean(\"value\") AS \"average\" FROM measurements.gilgo",
        "frequency": 1800  # 1800 seconds = 30 minutes
    },
    "query1": {
        "query": "SELECT field1 FROM measurement1",
        "frequency": 300  # 300 seconds = 5 minutes
    },
    "query2": {
        "query": "SELECT field2 FROM measurement2",
        "frequency": 600  # 600 seconds = 10 minutes
    },
    # Add more queries here...
}
