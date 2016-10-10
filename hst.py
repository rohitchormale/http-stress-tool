#!/usr/bin/env python

"""
`HTTP Stress Tool` aka `hst`
This is simple tool to test load/stress on HTTP servers.
Any malicious usage of this tool is prohibited.
Version 0.2 is heavily influenced by `hulk.py` - https://github.com/grafov/hulk


Configuration
    For simple usage, modify values of METHOD, URI, HEADERS & BODY.
    For advanced usage, override function `generateRequests`
    Number of requests to send can be configured using `REQUEST_TO_SEND`
    Interval between requests can be configured using `REQUSET_INTERVAL`

Run
    `python hst.py`

Dependencies
    Twisted

"""


__author__ = 'Rohit Chormale'
__version__ = '0.2'


import sys
import random
import re
import logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
from zope.interface import implements
from twisted.internet import reactor, defer, task
from twisted.internet.protocol import Protocol
from twisted.web.iweb import IBodyProducer
from twisted.web.client import Agent


# Number of request & interval between them
REQUESTS_INTERVAL = 0.00001
REQUESTS_TO_SEND = 1

# Sample json GET request
METHOD = "GET"
URI = "http://127.0.0.1:8080/test"
HEADERS = [
    ("Cache-Control", "no-cache"),
    ("Accept-Charset", 'ISO-8859-1,utf-8;q=0.7,*;q=0.7'),
    ("Keep-Alive", str(random.randint(110, 120))),
    ("Connection", "keep-alive"),
    ("Accept", "application/json"),
    ("Content-Type", "application/json"),
]
BODY = None
# For query string
# BODY = { "foo": "bar", "baz": "qux"}


"""
# Sample json POST request
import json
METHOD = "POST"
URI = "http://127.0.0.1:8080/test"
HEADERS = [
    ("Cache-Control", "no-cache"),
    ("Accept-Charset", 'ISO-8859-1,utf-8;q=0.7,*;q=0.7'),
    ("Keep-Alive", str(random.randint(110, 120))),
    ("Connection", "keep-alive"),
    ("Accept", "application/json"),
    ("Content-Type", "application/json"),
]
BODY = json.dumps({
   "foo": "bar",
    "baz": "qux",
    "qux": "foo",
})
"""




# ####### #
# HELPERS #
# ####### #

other_headers = [
    ("Cache-Control", "no-cache"),
    ("Accept-Charset", 'ISO-8859-1,utf-8;q=0.7,*;q=0.7'),
    ("Keep-Alive", random.randint(110, 120)),
    ("Connection", "keep-alive"),
]

json_headers = [
    ("Accept", "application/json"),
    ("Content-Type", "application/json"),
]


def get_random_user_agent():
    """return random user-agent header from available headers"""
    user_agents = [
        ('User-Agent', 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.1.3) Gecko/20090913 Firefox/3.5.3'),
        ('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en; rv:1.9.1.3) Gecko/20090824 Firefox/3.5.3 (.NET CLR 3.5.30729)'),
        ('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US; rv:1.9.1.3) Gecko/20090824 Firefox/3.5.3 (.NET CLR 3.5.30729)'),
        ('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.1) Gecko/20090718 Firefox/3.5.1'),
        ('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.6 Safari/532.1'),
        ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; WOW64; Trident/4.0; SLCC2; .NET CLR 2.0.50727; InfoPath.2)'),
        ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0; SLCC1; .NET CLR 2.0.50727; .NET CLR 1.1.4322; .NET CLR 3.5.30729; .NET CLR 3.0.30729)'),
        ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.2; Win64; x64; Trident/4.0)'),
        ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; SV1; .NET CLR 2.0.50727; InfoPath.2)'),
        ('User-Agent', 'Mozilla/5.0 (Windows; U; MSIE 7.0; Windows NT 6.0; en-US)'),
        ('User-Agent', 'Mozilla/4.0 (compatible; MSIE 6.1; Windows XP)'),
        ('User-Agent', 'Opera/9.80 (Windows NT 5.2; U; ru) Presto/2.5.22 Version/10.51'),
    ]
    return random.choice(user_agents)


def get_random_referrer(hosts=[]):
    """return random referrers from available referrers"""
    referrers = [
        'http://www.google.com/?q=',
        'http://www.usatoday.com/search/results?q=',
        'http://engadget.search.aol.com/search?q=',
    ]
    if hosts:
        for h in hosts:
            _referrer = 'http://' + h + '/'
            referrers.append(_referrer)
    referrer = random.choice(referrers) + build_block(random.randint(5, 10))
    return referrer

def build_block(size=5):
    block = ''
    for i in range(0, size):
        block += chr(random.randint(65, 90))
    return block


# ############ #
# Stress Tool #
# ########### #

class BodyProducer(object):
    implements(IBodyProducer)

    def __init__(self, data):
        self.data = data
        self.length = len(data)

    def startProducing(self, consumer):
        consumer.write(self.data)
        return defer.succeed(None)

    def stopProducing(self):
        pass

    def resumeProducing(self):
        pass

    def pauseProducing(self):
        pass


class BodyReceiver(Protocol):
    def __init__(self, df):
        self.exitDf = df
        self.buffer = []

    def connectionMade(self):
        pass

    def dataReceived(self, data):
        self.buffer.append(data)

    def connectionLost(self, reason):
        logging.debug("Finished receiving body - %s" % reason.getErrorMessage())
        self.exitDf.callback(self.buffer)


agent = Agent(reactor)
class HttpRequest(object):
    def __init__(self, method, uri, headers=None, body=None, requestDf=None):
        self.method = method.upper()
        self.headers = headers

        if self.method in ("GET", ) and body is not None and isinstance(body, dict):
            import urllib
            querystring = urllib.urlencode(body)
            self.uri = "?".join([uri, querystring])
            self.body = None
        else:
            self.uri = uri
            self.body = body

        if requestDf is None:
            self.requestDf = defer.Deferred()
        else:
            self.requestDf = requestDf

    def sendRequest(self):
        bodyProducer = None
        if self.body:
            bodyProducer = BodyProducer(self.body)
        logging.debug("Sending request | %s | %s" %(self.method,  self.uri))
        df = agent.request(self.method, self.uri, self.headers, bodyProducer)
        df.addCallback(self.onRequest)
        df.addErrback(self.errRequest)

    def onRequest(self, response):
        logging.debug("Request successful | %s" % response)
        response.deliverBody(BodyReceiver(self.requestDf))

    def errRequest(self, error):
        logging.error("Request failed | %s" % error)
        self.requestDf.callback(error)


requestQueue = []
def handleRequestsQueue():
    """This function handles callback called after all requests are finished (Request might be finished successfully or not.
    TODO - Generate stats
    """
    def success(result):
        logging.info("Done")
        reactor.stop()

    def failure(error):
        logging.error(error)
        reactor.stop()

    queueDf = defer.DeferredList(requestQueue)
    queueDf.addCallback(success)
    queueDf.addErrback(failure)


def sendHttpRequest(uri, method, headers=None, body=None, requestDf=None):
    """ This function provides actual API to send HTTP requests.
    For GET request, send query string as body in dictionary format.
    This dictionary will be converted in query string.
    uri - valid HTTP uri
    method - GET, POST, PUT
    headers - valid HTTP headers
    body - valid HTTP body or None. For GET request, body will be converted in query string
    requestDf - `twisted.defer.Deferred` object or None"""
    httpRequest = HttpRequest(uri, method, headers, body, requestDf)
    httpRequest.sendRequest()
    return httpRequest.requestDf


def generateRequests():
    """Override this function to customize requests.
    This function will be called after each `REQUEST_INTERVAL.
    MUST return deferred came from sendHttpRequests
    TODO - Add more example of customization
    """
    def onRequest(response):
        logging.info(response)

    def errRequest(error):
        logging.error(error)

    global METHOD, URI, HEADERS, BODY
    host_pattern = "http?s\://([^/]*)/?.*"
    match = re.search(host_pattern, URI)
    if match:
        host = match.group(1)
    else:
        host = None
    _headers = HEADERS[::]
    headers_dict = dict(HEADERS)
    if 'User-Agent' not in headers_dict:
        _headers.append(get_random_user_agent())
    if 'Referrer' not in headers_dict:
        _headers.append(get_random_referrer())
    if 'Host' not in headers_dict and host:
        _headers.append(host)

    requestDf = defer.Deferred()
    requestDf.addCallback(onRequest)
    requestDf.addErrback(errRequest)

    from twisted.web.http_headers import Headers
    headers = Headers()
    for h in _headers:
        headers.addRawHeader(h[0], h[1])
    return sendHttpRequest(METHOD, URI, headers, BODY, requestDf)


def _generateRequests():
    """Don't override this function, unless you know what you're doing.
    This function is added to provide abstraction for customizing request"""
    requestDf = generateRequests()
    requestQueue.append(requestDf)
    if len(requestQueue) == REQUESTS_TO_SEND:
        requestLoop.stop()
        handleRequestsQueue()


requestLoop = task.LoopingCall(_generateRequests)
requestLoop.start(REQUESTS_INTERVAL)


def main():
    reactor.run()


if __name__ == '__main__':
    main()
