# Gunicorn production configuration
timeout = 120
workers = 2
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
