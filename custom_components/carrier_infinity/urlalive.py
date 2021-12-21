#
# /time URL handling
#
# This returns a simple plain text response and is checked by the thermostat
# periodically.
#

from httpobj import HttpRequest, HttpResponse, addUrl


def urlAlive(request):

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "private, no-transform"))
    response.addContentLengthHeader(5)
    response.addContentTypeHeader("text/plain; charset=utf-8")
    response.addServerHeader()
    response.addRequestContextHeader()
    response.addAccessControlHeader()
    response.addDateHeader()

    response.body = "alive"

    return response

addUrl("/Alive$", urlAlive)
