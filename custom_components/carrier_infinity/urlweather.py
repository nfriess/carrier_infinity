#
# /weather URL handling
#
# Currently this just proxies the request to Carrier's server.
# It is also logging the XML content so we can learn what the format of
# responses is.
#

import logging
import requests

from .httpobj import HttpRequest, HttpResponse, addUrl

_LOGGER: logging.Logger = logging.getLogger(__package__)

def urlWeather(request):

    postalCode = request.pathDict['postalCode']

    host_url = "http://{}/weather/{}/forecast".format(request.host, postalCode)

    cliResp = requests.request(
        method=request.method,
        url=host_url,
        headers={key: value for (key, value) in request.headers if key != 'Host'},
        data=request.body,
        allow_redirects=False)

    if cliResp.status_code != 200:
        return HttpResponse.errorResponse(cliResp.status_code, "Message")

    _LOGGER.info(cliResp.text)

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "private"))
    response.addContentLengthHeader(len(cliResp.text))
    response.addContentTypeHeader("application/xml; charset=utf-8")
    response.addServerHeader()
    response.addRequestContextHeader()
    response.addAccessControlHeader()
    response.addDateHeader()

    response.body = cliResp.text

    return response


addUrl("/weather/(?P<postalCode>.+)/forecast$", urlWeather)
