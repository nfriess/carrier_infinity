#
# http://*
#
# The thermostat downloads release notes using a full URL.  This
# module replies to any full URL request with a simple text file
# to replace the official release nodes.
#

import logging

from httpobj import HttpRequest, HttpResponse, addUrl

def urlRelNodes(request):

    hostAndPath = request.pathDict['hostAndPath']

    logging.info("Fetch http://{}".format(hostAndPath))

    bodyStr = "Returned from python server"

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "no-store,no-cache"))
    response.headers.append(("Pragma", "no-cache"))
    response.addContentLengthHeader(len(bodyStr))
    response.addContentTypeHeader("text/plain")
    response.addRequestContextHeader()
    response.headers.append(("X-Content-CRC", "1278"))
    response.headers.append(("X-Current-Page", "http://{}".format(hostAndPath)))
    # Cookie
    response.addDateHeader()

    response.body = bodyStr

    return response



addUrl("http://(?P<hostAndPath>.+)$", urlRelNodes)
