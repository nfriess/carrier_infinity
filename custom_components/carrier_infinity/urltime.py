#
# /time URL handling
#
# This returns the current date and time.
#

from datetime import datetime

from httpobj import HttpRequest, HttpResponse, addUrl

def urlTime(request):

    utc = datetime.utcnow()
    strDate = utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    timeXmlStr = '<time version="1.42" xmlns:atom="http://www.w3.org/2005/Atom"><atom:link rel="self" href="http://www.api.ing.carrier.com/time/"/><utc>'
    timeXmlStr += strDate
    timeXmlStr += '</utc></time>'

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "private"))
    response.addContentLengthHeader(len(timeXmlStr))
    response.addContentTypeHeader("application/xml; charset=utf-8")
    response.addServerHeader()
    response.addRequestContextHeader()
    response.addAccessControlHeader()
    response.addDateHeader()

    response.body = timeXmlStr

    return response


addUrl("/time/", urlTime)
