#
# /manifest URL handling
#
# The thermostat loads the manifest when it starts up a wifi connection.
# We treat the manifest as a static blob that we send back to the Thermostat
# as-is.
#

from datetime import datetime

from httpobj import HttpRequest, HttpResponse, addUrl


responseManifest = None

def loadXMLFiles():

	global responseManifest

	responseManifest = ""
	with open("manifest.xml", 'r') as fhan:
		for line in fhan:
			responseManifest = responseManifest + line


loadXMLFiles()




def urlManifest(request):

    global responseManifest

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "no-store,no-cache"))
    response.headers.append(("Pragma", "no-cache"))
    response.addContentLengthHeader(len(responseManifest))
    response.addContentTypeHeader("application/xml")
    response.addRequestContextHeader()
    # Set-cookie header
    response.addDateHeader()

    response.body = responseManifest

    return response


addUrl("/manifest", urlManifest)
