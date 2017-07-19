#!/usr/bin/python3.6
import calendar

import requests
import argparse
import datetime
import json
import socket
import threading
import time
import uuid
from math import trunc
from pprint import pprint
from urllib.parse import urlencode, quote_plus


def ts():
    return f'[{datetime.datetime.now()}]'


class GraylogTest:
    def __init__(self, options):
        self.options = options
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.sent_count = 0
            self.failed_count = 0
            self.validated_count = 0
            self.created_count = 0
            self.group_id = str(uuid.uuid4())
            self.start_time = time.time()

    def getSentSuccessRatio(self):
        return self.validated_count / self.sent_count

    def getRequestedSuccessRatio(self):
        return self.sent_count / self.options.total_requests

    # Slam Graylog with some data and validate all requests
    def run(self, use_udp=False):
        self.reset()
        sender = self.__send_udp if use_udp else self.__send_tcp
        mode_text = "UDP" if use_udp else "TCP"
        total_requests = self.options.total_requests

        # Send requests
        print(f'{ts()} Sending {total_requests} requests with {mode_text} for group {self.group_id}')
        if self.options.threads <= 1:
            print(f'{ts()} Sending in single threaded mode')
            sender(total_requests)
        else:
            print(f'{ts()} Sending in multi threaded mode with {self.options.threads} threads')
            skip = 0
            batch_size = trunc(total_requests / self.options.threads)
            while skip < total_requests:
                threads = []
                for x in range(self.options.threads):
                    remain = total_requests - skip
                    take = batch_size if batch_size <= remain else remain
                    thread = threading.Thread(target=sender, args=(take,))
                    threads.append(thread)
                    skip += take

                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

        duration = (time.time() - self.start_time)
        mps = trunc(total_requests / duration)
        print(f'{ts()} Sent [{total_requests}] requests with {mode_text} in [{duration}] sec ({mps} msg/s)')

        # Wait for flush
        print(f'{ts()} Waiting for Graylog to flush logs...')
        time.sleep(10)

        # Validate result
        self.__validate()
        self.end_time = time.time()

    def __validate(self):
        total_requests = self.options.total_requests
        url_encoded_query = urlencode({'query': f'"{self.group_id}"'}, quote_via=quote_plus)
        port = self.options.api_port
        host = self.options.host
        proto = self.options.protocol
        search_url = f'{proto}://{host}:{port}/api/search/universal/relative?{url_encoded_query}&range=0&limit=1'
        if self.options.verbosity >= 1:
            print(f'{ts()} Validating sent data -> {search_url}')

        headers = {'Accept': 'application/json'}
        res = requests.get(search_url, auth=api_auth, verify=False, headers=headers)
        if res.status_code != 200:
            print(f'{ts()} Request failed -> status - {res.status_code}:{res.text}')
            return

        data = res.text
        response_json = json.loads(data)
        if self.options.verbosity >= 1:
            exec_time = res.elapsed.total_seconds()
            print(f'{ts()} {search_url} request execution time {exec_time}')

        with self.lock:
            if 'total_results' in response_json:
                self.validated_count = response_json['total_results']
                valid_ratio = self.getSentSuccessRatio() * 100
                print(f'{ts()} [{total_requests}] requests generated - '
                      f'[{self.sent_count}] sent - '
                      f'[{self.validated_count}] ({trunc(valid_ratio)}%) validated')
            else:
                self.validated_count = 0
                print(f'{ts()} Request failed - Missing results -> {res.text}')

    def __create_message(self):
        with self.lock:
            self.created_count += 1
            return {
                'version': '1.1',
                'host': 'example.org',
                'short_message': 'this is the short message',
                'full_message': 'Backtrace here\n\nmore stuff',
                'timestamp': calendar.timegm(time.gmtime()),
                'level': 1,
                '_datetime': str(datetime.datetime.now()),
                '_message_id': str(uuid.uuid4()),
                '_group_id': self.group_id,
                '_sequence': self.created_count

            }

    def __throttle(self, suspend_ms):
        if self.options.verbosity >= 2:
            print(f'{ts()} Throttled TCP send for {suspend_ms}')
        time.sleep(suspend_ms / 1000)

    def __send_udp(self, send_count):
        for x in range(send_count):
            start = time.time()
            message = self.__create_message()
            req_id = message['_message_id']
            host = self.options.host
            port = self.options.log_send_port
            json_message = json.dumps(message)
            json_bytes = bytes(json_message, 'utf-8')
            try:
                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_sock.sendto(json_bytes, (host, port))
                duration = time.time() - start

                if self.options.throttle > 0 and duration < self.options.throttle:
                    self.__throttle(self.options.throttle - duration)

                if self.options.verbosity >= 2:
                    mps = 1 / duration
                    print(f'{ts()} Test {self.group_id} - Sent UDP message {req_id} -> '
                          f'{host}:{port} in [{duration}] sec ({mps} msg/s)')

                with self.lock:
                    self.sent_count += 1
                    if self.sent_count % (self.options.total_requests * .01) == 0:
                        mps = trunc(self.sent_count / (time.time() - self.start_time))
                        progress = trunc(self.sent_count / self.options.total_requests * 100)
                        print(f'{ts()} UDP Send progress: {progress}%  ({mps} msg/s)')

            except Exception as ex:
                print(f'{ts()} Error - UDP Request {req_id} failed -> {ex}')
                with self.lock:
                    self.failed_count += 1

    def __send_tcp(self, send_count):
        for x in range(send_count):
            start = time.time()
            message = self.__create_message()
            req_id = message['_message_id']
            host = self.options.host
            port = self.options.log_send_port
            json_message = json.dumps(message)
            json_bytes = json_message.encode('utf-8') + b'\x00'
            try:
                tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_sock.connect((host, port))
                tcp_sock.sendall(json_bytes)
                tcp_sock.close()
                duration = time.time() - start

                if self.options.throttle > 0 and duration < self.options.throttle:
                    self.__throttle(self.options.throttle - duration)

                if self.options.verbosity >= 2:
                    mps = 1 / duration
                    print(f'{ts()} Test {self.group_id} - Sent TCP message {req_id} -> '
                          f'{host}:{port} in [{duration}] sec ({mps} msg/s)')

                with self.lock:
                    self.sent_count += 1
                    if self.sent_count % (self.options.total_requests * .01) == 0:
                        mps = trunc(self.sent_count / (time.time() - self.start_time))
                        progress = trunc(self.sent_count / self.options.total_requests * 100)
                        print(f'{ts()} TCP Send progress: {progress}% ({mps} msg/s)')

            except Exception as ex:
                print(f'{ts()} Error - TCP Request {req_id} failed -> {ex}')
                with self.lock:
                    self.failed_count += 1


parser = argparse.ArgumentParser(description='Test Graylog UDP and TCP.')

parser.add_argument("-H", "--host", type=str, default="localhost",
                    help="The Graylog hostname")

parser.add_argument("-l", "--log_send_port", type=int, default=12201,
                    help="The Graylog TCP/UDP logging port")

parser.add_argument("-r", "--throttle", type=float, default=0,
                    help="Throttle the minimum time between requests in milliseconds")

parser.add_argument("-a", "--api_port", type=int, default=9000,
                    help="The Graylog REST API port")

parser.add_argument("-P", "--protocol", type=str, choices=['http', 'https'], default="http",
                    help="The Graylog REST API protocol")

parser.add_argument("-u", "--username", type=str, default="admin",
                    help="The Graylog REST API username")

parser.add_argument("-p", "--password", type=str, default="admin",
                    help="The Graylog REST API password")

parser.add_argument("-t", "--total_requests", type=int, default=1000,
                    help="The total number of test requests to send to Graylog")

parser.add_argument("-T", "--threads", type=int, default=1,
                    help="The total number of send threads to run")

parser.add_argument("-m", "--mode", nargs='+', choices=['UDP', 'TCP'], default=['UDP', 'TCP'],
                    help='Specifies the send mode (TCP or UDP or BOTH)')

parser.add_argument("-v", "--verbosity", action="count", default=0,
                    help="Application output verbosity")

args = parser.parse_args()

# Get parsed args
api_auth = requests.auth.HTTPBasicAuth(args.username, args.password)
args.password = '**redacted**'
if args.threads < 1:
    args.threads = 1

if args.verbosity >= 1:
    print(f'{ts()} Execution arguments')
    pprint(vars(args))

# Print stats
test = GraylogTest(args)
if "UDP" in args.mode:
    test.run(use_udp=True)

time.sleep(5)
if "TCP" in args.mode:
    test.run(use_udp=False)

print(f'{ts()} Test completed in [{test.end_time - test.start_time}] sec')
