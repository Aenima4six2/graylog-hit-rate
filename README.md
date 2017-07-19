# graylog-delivery-ratio
Send lots of GELF messages to Graylog and get the success/fail delivery ratio.

~~~~ 
usage: test_delivery_ratio.py [-h] [-H HOST] [-l LOG_SEND_PORT] [-r THROTTLE]
                              [-a API_PORT] [-P {http,https}] [-u USERNAME]
                              [-p PASSWORD] [-t TOTAL_REQUESTS] [-T THREADS]
                              [-m {UDP,TCP,HTTP} [{UDP,TCP,HTTP} ...]] [-v]

Send lots of GELF messages to Graylog and get the success/fail delivery ratio.

optional arguments:
  -h, --help            show this help message and exit
  -H HOST, --host HOST  The Graylog hostname
  -l LOG_SEND_PORT, --log_send_port LOG_SEND_PORT
                        The Graylog TCP/UDP logging port
  -r THROTTLE, --throttle THROTTLE
                        Throttle the minimum time between requests in
                        milliseconds
  -a API_PORT, --api_port API_PORT
                        The Graylog REST API port
  -P {http,https}, --protocol {http,https}
                        The Graylog REST API protocol
  -u USERNAME, --username USERNAME
                        The Graylog REST API username
  -p PASSWORD, --password PASSWORD
                        The Graylog REST API password
  -t TOTAL_REQUESTS, --total_requests TOTAL_REQUESTS
                        The total number of test requests to send to Graylog
  -T THREADS, --threads THREADS
                        The total number of send threads to run
  -m {UDP,TCP,HTTP} [{UDP,TCP,HTTP} ...], --mode {UDP,TCP,HTTP} [{UDP,TCP,HTTP} ...]
                        Specifies the send mode (TCP or UDP or BOTH)
  -v, --verbosity       Application output verbosity
  ~~~~ 
