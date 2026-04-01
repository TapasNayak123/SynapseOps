{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# SynapseOps ECS POC Dashboard\nTracks the SynapseOps ECS service, ALB behavior, upstream auth-api-poc errors, and AgentCore runtime logs."
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "ECS Service Utilization",
        "region": "__AWS_REGION__",
        "view": "timeSeries",
        "stacked": false,
        "stat": "Average",
        "period": 300,
        "metrics": [
          [ "AWS/ECS", "CPUUtilization", "ClusterName", "__ECS_CLUSTER__", "ServiceName", "__ECS_SERVICE__", { "label": "CPU %" } ],
          [ ".", "MemoryUtilization", ".", ".", ".", ".", { "label": "Memory %" } ]
        ]
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "ALB Traffic And Latency",
        "region": "__AWS_REGION__",
        "view": "timeSeries",
        "stacked": false,
        "stat": "Sum",
        "period": 300,
        "metrics": [
          [ "AWS/ApplicationELB", "RequestCount", "LoadBalancer", "__LOAD_BALANCER_DIMENSION__", { "label": "Request count" } ],
          [ ".", "HTTPCode_Target_5XX_Count", ".", ".", { "label": "Target 5XX" } ],
          [ ".", "HTTPCode_Target_4XX_Count", ".", ".", { "label": "Target 4XX" } ],
          [ ".", "TargetResponseTime", ".", ".", { "label": "Target response time", "stat": "Average", "yAxis": "right" } ]
        ]
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "ALB Target Health",
        "region": "__AWS_REGION__",
        "view": "timeSeries",
        "stacked": false,
        "period": 300,
        "metrics": [
          [ "AWS/ApplicationELB", "HealthyHostCount", "TargetGroup", "__TARGET_GROUP_DIMENSION__", "LoadBalancer", "__LOAD_BALANCER_DIMENSION__", { "label": "Healthy hosts", "stat": "Average" } ],
          [ ".", "UnHealthyHostCount", ".", ".", ".", ".", { "label": "Unhealthy hosts", "stat": "Average" } ]
        ]
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 14,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "auth-api-poc Recent Errors",
        "region": "__AWS_REGION__",
        "view": "table",
        "query": "SOURCE '__MONITORED_LOG_GROUP__' | fields @timestamp, path, method, statusCode, errorCode, message, correlationId | filter statusCode >= 400 or level = 'error' or message = 'Error occurred' | sort @timestamp desc | limit 100"
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 20,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "auth-api-poc Slow Requests",
        "region": "__AWS_REGION__",
        "view": "table",
        "query": "SOURCE '__MONITORED_LOG_GROUP__' | fields @timestamp, path, method, duration, statusCode, message | filter message = 'Request completed' and duration != '' | parse duration /(?<durationMs>\\d+)/ | filter durationMs > 2000 | sort @timestamp desc | limit 100"
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 26,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "SynapseOps Runtime Logs",
        "region": "__AWS_REGION__",
        "view": "table",
        "query": "SOURCE '__SYNAPSE_LOG_GROUP__' | fields @timestamp, @message | sort @timestamp desc | limit 100"
      }
    }
  ]
}