#
# This main HTTP server that the theromostat will interact with.  This
# is callable as a main module.
#

import logging
import os
import socketserver
import time
import traceback

from httpobj import HttpRequest, HttpResponse, configuredURLs
import urlalive
import urlsystems
import urlweather
import urltime
import urlmanifest
import urlapi
import urlrelnodes



class MyTCPHandler(socketserver.StreamRequestHandler):

        #def setup(self):
        #    self.timeout = 5
        #    super(socketserver.StreamRequestHandler, self).setup()

        # Based on experimentation it appears that if a response header crosses
        # a TCP packet boundary the thermostat isn't able to parse the response
        # and gives up.  This method allows us to get around that limitation
        # by trying to send response headers at a slow enough rate that our
        # OS will PUSH each header as its own TCP packet.
        def writeLine(self, line):
            line = line + "\r\n"
            self.wfile.write(line.encode("utf-8"))
            self.wfile.flush()
            time.sleep(0.01)

        # Convenience method to send error responses.
        def errorResponse(self, errCode, errMessage):
            logging.warning("  Respond {}".format(errCode))
            self.writeLine("{} {} {}".format(HttpRequest.VERSION_1_1, errCode, errMessage))
            self.writeLine("Content-Length: 0")
            self.writeLine("Connection: close")
            self.writeLine("")

        def parseHttpRequest(self):

            first_line = self.rfile.readline().decode("utf-8")
            (http_method, http_path, http_version) = first_line.strip().split(" ")

            if not http_version == HttpRequest.VERSION_1_1:
                self.sendResponse(HttpRequest(http_version, http_method, http_path, ""), HttpResponse.errorResponse(400, "Bad Request"))
                return None

            http_query_string = None
            if '?' in http_path:
                (http_path, http_query_string) = http_path.split("?", 1)

            httpRequestObj = HttpRequest(http_version, http_method, http_path, http_query_string)

            next_line = self.rfile.readline().decode("utf-8")
            while not next_line == "\r\n":

                (k, v) = next_line.split(":", 1)

                # Remove space after : and \r\n at the end
                v = v[1:]
                v = v[:-2]

                httpRequestObj.headers.append((k, v))

                next_line = self.rfile.readline().decode("utf-8")

            # Saw \r\n line, read body

            try:
                httpRequestObj.parseHeaders()
            except:
                traceback.print_exc()
                self.sendResponse(httpRequestObj, HttpResponse.errorResponse(400, "Bad Request"))
                return None

            if http_method == HttpRequest.METHOD_POST:

                if not httpRequestObj.contentLength or not httpRequestObj.contentType:
                    return httpRequestObj

                # We use a non-blocking socket and set a timeout to try and limit
                # the chance of thermostat from locking up our server.  Ideally
                # we should have done the same when reading the headers.
                self.connection.setblocking(0)
                numLeft = httpRequestObj.contentLength
                timeLeft = 15 * 10

                httpRequestObj.body = ""

                while numLeft > 0:
                    bytesRead = self.rfile.read1(numLeft)

                    if not bytesRead:
                        if timeLeft == 0:
                            logging.warning("  Timeout witing for body, need {} more bytes".format(numLeft))
                            self.sendResponse(httpRequestObj, HttpResponse.errorResponse(400, "Bad Request"))
                            return None

                        time.sleep(0.1)
                        timeLeft = timeLeft - 1
                        continue

                    httpRequestObj.body = httpRequestObj.body + bytesRead.decode("utf-8")
                    numLeft = numLeft - len(bytesRead)

                if not bytesRead and numLeft > 0:
                    logging.warning("  Need {} more bytes from body".format(numLeft))
                    self.sendResponse(httpRequestObj, HttpResponse.errorResponse(400, "Bad Request"))
                    return None

                httpRequestObj.parseBody()

            return httpRequestObj


        def sendResponse(self, httpRequestObj, httpResponseObj):

            logBodyStr = "None"

            if httpResponseObj.body:
                if len(httpResponseObj.body) < 50:
                    logBodyStr = httpResponseObj.body
                else:
                    logBodyStr = str(len(httpResponseObj.body)) + " bytes"

            # A basic access log
            logging.info("Request from {}:{} {} {} {} {}".format(self.client_address[0], self.client_address[1], httpRequestObj.method, httpRequestObj.path, httpResponseObj.code, logBodyStr))

            self.writeLine("{} {} {}".format(HttpRequest.VERSION_1_1, httpResponseObj.code, httpResponseObj.message))

            connectionClose = False
            for (name, value) in httpResponseObj.headers:
                self.writeLine("{}: {}".format(name, value))
                if name == "Connection":
                    connectionClose = True
            self.writeLine("")

            if httpResponseObj.body:
                # The thermostat can also reject a response if the body crosses
                # a TCP packet in certain places.  Using the built-in self.wfile
                # object seems to be problematic.  So here we use the underlying
                # socket and try to blast the body out using the low-level
                # os.write() call.
                self.connection.setblocking(1)
                fileno = self.connection.detach()
                try:
                    dataToSend = httpResponseObj.body.encode("utf-8")
                except:
                    dataToSend = httpResponseObj.body
                os.write(fileno, dataToSend)


        def handle(self):

            httpRequestObj = self.parseHttpRequest()
            if not httpRequestObj:
                return

            httpResponseObj = None

            for (pathRe, actionFunc) in configuredURLs:
                m = pathRe.match(httpRequestObj.path)
                if m:
                    httpRequestObj.pathGroup = m.groups()
                    httpRequestObj.pathDict = m.groupdict()
                    try:
                        httpResponseObj = actionFunc(httpRequestObj)
                    except:
                        traceback.print_exc()
                        self.sendResponse(httpRequestObj, HttpResponse.errorResponse(503, "Exception thrown"))
                        return
                    break

            if not httpResponseObj:
                self.sendResponse(httpRequestObj, HttpResponse.errorResponse(404, "Not Found"))
                return

            # Simulate delay from Internet 100ms, seems to help the theromostat
            # accept the response.
            time.sleep(0.1)

            self.sendResponse(httpRequestObj, httpResponseObj)



class MyTCPServer(socketserver.TCPServer):

    def server_bind(self):
        self.allow_reuse_address = True
        super(MyTCPServer, self).server_bind()


if __name__ == "__main__":
  HOST, PORT = "0.0.0.0", 5000

  logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

  with MyTCPServer((HOST, PORT), MyTCPHandler) as server:
    try:
        logging.info("Listen on port {}".format(PORT))
        server.serve_forever()
    except:
        server.server_close()
