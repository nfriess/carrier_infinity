#
# This module contains data objects and helpers that are referenced in the
# HTTP server and the individual URL handlers.
#

from datetime import datetime
import re
from urllib.parse import parse_qs
import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)

# This is populated by the URL handlers to define the mapping between a path
# and the function that should be called.  This is an ordered list because
# we may have more specific regular expressions that match before more generic
# ones (like in /systems paths).
configuredURLs = []

# Called by URL handler modules to add URL handlers.
# Arguments:
#  reStr: A regular expression to match URLs
#  func:  A function that accepts an HttpRequest object as input
#         and returns an HttpReponse object.
#
def addUrl(reStr, func):
    global configuredURLs
    configuredURLs.append((re.compile(reStr), func))

#
# Filled in by the HTTP server and provided to URL handlers to contain the
# the HTTP request information.
#
class HttpRequest:

    VERSION_1_1 = "HTTP/1.1"

    METHOD_GET = "GET"
    METHOD_POST = "POST"

    def __init__(self, version, method, path, queryString):
        # Always VERSION_1_1:
        self.version = version
        # One of hte METHOD_ constants
        self.method = method
        # The path portion of the request
        self.path = path
        # If the matching RE for this handler contains any groupings, this
        # will be the .groups list of the matcher.
        self.pathGroup = []
        # If the matching RE for this handler contains any named groups, this
        # will contain a map from the .groupdict of the matcher.
        self.pathDict = {}
        # If there was a query string after the path then this will contain
        # a map of data.  See: urllib.parse.parse_qs
        self.queryString = queryString
        if queryString:
            self.queryString = parse_qs(queryString, keep_blank_values=True)
        # An ordered list of (name, value) for each request header
        self.headers = []

        # If there is a Content-Length header, this will contain the int value
        self.contentLength = None
        # If there is a Content-Type header, this will contain the value string
        self.contentType = None
        # If there is a Host header, this will contain the value string
        self.host = None

        # If there is a POST body, this will contain the raw string
        self.body = None
        # If the Content-Type is "application/x-www-form-urlencoded", this
        # will contain a parsed map of data.  See: urllib.parse.parse_qs
        self.bodyDict = None


    def parseHeaders(self):

        for (k, v) in self.headers:
            k = k.lower()
            if k == "content-length":
                if self.contentLength:
                    raise Exception("Duplicate Content-Length header")
                self.contentLength = int(v)
            elif k == "content-type":
                if self.contentType:
                    raise Exception("Duplicate Content-Type header")
                self.contentType = v
            elif k == "host":
                if self.host:
                    raise Exception("Duplicate Host header")
                self.host = v

    def parseBody(self):

        contentType = self.contentType.lower()

        if contentType == "application/x-www-form-urlencoded":
            self.bodyDict = parse_qs(self.body, keep_blank_values=True)
        else:
            raise Exception(f"Unhandled content-type: {contentType}")



#
# Filled in by a URL handler and returned in its function call, used by
# the HTTP server to build a response to the client.
#
class HttpResponse:

    def __init__(self, code, message):
        # The int code and string message of the first response line
        self.code = code
        self.message = message
        # An ordered list of (name, value) for each response header
        self.headers = []
        # If the response should contain a body then this should be a string
        # with the body content.
        self.body = None

    # These are some common headers added by the real HTTP server.  In some cases
    # there is hard-coded data determined by trial and error.
    def addDateHeader(self):
        utc = datetime.utcnow()
        strDate = utc.strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.headers.append(("Date", strDate))

    def addContentTypeHeader(self, contentType):
        self.headers.append(("Content-Type", contentType))

    def addContentLengthHeader(self, contentLength):
        self.headers.append(("Content-Length", str(contentLength)))

    def addServerHeader(self):
        self.headers.append(("Server", "Microsoft-IIS/10.0"))

    def addRequestContextHeader(self):
        self.headers.append(("Resquest-Context", "appId=cid-v1:1a3678a3-b034-4acb-aa91-edbdfa374c13"))

    def addAccessControlHeader(self):
        self.headers.append(("Access-Control-Expose-Headers", "Request-Context"))

    # Static helper function to create an HttpResponse for error responses
    def errorResponse(code, message):
        return HttpResponse(code, message)

    # Static helper function to create an HttpResponse for 200 OK responses
    def okResponse():
        return HttpResponse(200, "OK")
