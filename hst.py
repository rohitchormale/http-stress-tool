#!/usr/bin/env python

"""
`HTTP Stress Tool` aka `hst`
This is simple tool to test load/stress on HTTP servers.

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


import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
from zope.interface import implements
from twisted.internet import reactor, defer, task
from twisted.internet.protocol import Protocol
from twisted.web.iweb import IBodyProducer
from twisted.web.client import Agent


# Sample POST request
METHOD = "POST"
URI = "http://127.0.0.1:8080/test"
HEADERS = {
    ('Accept', 'application/json'),
    ('Content-Type', 'application/json'),
}
import json
BODY = json.dumps({
   "foo": "bar",
    "baz": "qux",
    "qux": "foo",
})
REQUESTS_INTERVAL = 0.00001
REQUESTS_TO_SEND = 100


"""
# Sample GET request
METHOD = "POST"
URI = "http://127.0.0.1:8080/test"
body = None

# For query string
# body = { 'foo': 'bar', 'baz': 'qux'}
"""



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
        if self.body:
            bodyProducer = BodyProducer(self.body)
        df = agent.request(self.method, self.uri, self.headers, bodyProducer)
        df.addCallback(self.onRequest)
        df.addErrback(self.errRequest)

    def onRequest(self, response):
        logging.debug("Request successful | %s" % response)
        response.deliverBody(BodyReceiver(self.requestDf))

    def errRequest(self, error):
        logging.error("Request failed | %s" % str(error))
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

    requestDf = defer.Deferred()
    requestDf.addCallback(onRequest)
    requestDf.addErrback(errRequest)

    from twisted.web.http_headers import Headers
    headers = Headers()
    for h in HEADERS:
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
