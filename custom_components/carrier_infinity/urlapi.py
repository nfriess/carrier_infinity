#
# /api URL handling
#
# This module is not part of the thermostat interface, but is here as a basic
# REST API to control the thermostat.
#

from datetime import datetime, timedelta
import json
import logging
import xml.etree.ElementTree as ET

from httpobj import HttpRequest, HttpResponse, addUrl

import urlsystems


# This is probably not localized and therefore is a static list
INFINITY_WEEKDAY_IDS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday"
]


def makeApiResponse(code, message, body, contentType=None):

    if code == 200:
        response = HttpResponse.okResponse()
    else:
        response = HttpResponse.errorResponse(code, message)

    if body:
        response.addContentLengthHeader(len(body))
        response.addContentTypeHeader(contentType)
        response.body = body

    response.addDateHeader()

    return response


def findNextActivity(periods, now):

    periodStart = datetime.now()

    periodIdList = list(periods)
    periodIdList.sort()

    for periodId in periodIdList:
        period = periods[periodId]

        if not period["enabled"]:
            continue

        (hour, minute) = period["time"].split(":", 1)
        periodStart = periodStart.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)

        if now < periodStart:
            return period["time"]

    return None


def urlApiZoneSetHold(request):

    global INFINITY_WEEKDAY_IDS

    zoneId = request.pathDict['zoneId']

    holdValue = False
    if "hold" in request.bodyDict:
        holdValue = (request.bodyDict['hold'][0] == "on")

    activityValue = None
    if "activity" in request.bodyDict:
        activityValue = request.bodyDict['activity'][0]

    untilValue = None
    if "until" in request.bodyDict:
        untilValue = request.bodyDict['until'][0]

    tempValue = None
    if "temp" in request.bodyDict:
        tempValue = request.bodyDict['temp'][0]

    if not holdValue:
        urlsystems.pendingActionHold = True
        urlsystems.pendingActionActivity = None
        urlsystems.pendingActionTemp = None
        logging.info("Set pending hold=off")
        return makeApiResponse(200, "OK", None)

    if not activityValue or activityValue not in ("home", "away", "sleep", "wake", "manual"):
        logging.info("Bad activity value: %s", activityValue)
        return makeApiResponse(400, "Bad activity value", None)

    if untilValue:

        parts = untilValue.split(":")
        if len(parts) != 2 or len(parts[1]) != 2:
            logging.info("Bad until value: %s", untilValue)
            return makeApiResponse(400, "Bad until value", None)

        hourVal = int(parts[0])
        minuteVal = int(parts[1])

        if hourVal > 23 or hourVal < 0 or minuteVal > 59 or minuteVal < 0:
            logging.info("Bad until value: %s", untilValue)
            return makeApiResponse(400, "Bad until value", None)

        if minuteVal not in (0, 15, 30, 45):
            logging.info("until minute must be in 15 min increments: %s", untilValue)
            return makeApiResponse(400, "until minute must be in 15 min increments", None)

    else:

        if zoneId not in urlsystems.configZones:
            logging.info("Missing until value and no zone config")
            return makeApiResponse(400, "Missing until value and no zone config", None)

        zoneConfig = urlsystems.configZones[zoneId]

        now = datetime.now()
        weekdayId = INFINITY_WEEKDAY_IDS[now.weekday()]

        periods = zoneConfig["schedule"][weekdayId]

        activityEnd = findNextActivity(periods, now)

        if not activityEnd:
            # Next day

            tomorrow = now + timedelta(days=1)

            tomorrow.replace(hour=0, minute=0)

            activityEnd = findNextActivity(periods, now)

            if not activityEnd:
                logging.info("Missing until value and cannot find next activity")
                return makeApiResponse(400, "Missing until value and cannot find next activity", None)

        untilValue = activityEnd


    if activityValue == "manual":

        if not tempValue:
            logging.info("Missing temp value for manual")
            return makeApiResponse(400, "Missing temp value for manual", None)

        tempValue = float(tempValue)

        if tempValue < 16 or tempValue > 24:
            logging.info("temp value outside of range: %s", tempValue)
            return makeApiResponse(400, "temp value outside of range", None)

        testVal = tempValue * 2
        if not testVal.is_integer():
            logging.info("temp value must be in 0.5 increments: %s", tempValue)
            return makeApiResponse(400, "temp value must be 0.5 increments", None)


    urlsystems.pendingActionHold = True
    urlsystems.pendingActionActivity = activityValue
    urlsystems.pendingActionUntil = untilValue
    urlsystems.pendingActionTemp = tempValue

    logging.info("Set pending hold=on to {} until {} temp {}".format(urlsystems.pendingActionActivity, urlsystems.pendingActionUntil, urlsystems.pendingActionTemp))

    return makeApiResponse(200, "OK", None)


addUrl("/api/hold/(?P<zoneId>.+)$", urlApiZoneSetHold)




def urlApiGetZoneField(request):

    zoneId = request.pathDict['zoneId']
    fieldName = request.pathDict['fieldName']

    if zoneId not in urlsystems.statusZones:
        return makeApiResponse(404, "No data", None)

    zoneObj = urlsystems.statusZones[zoneId]

    if fieldName not in zoneObj:
        return makeApiResponse(404, "No such field", None)

    return makeApiResponse(200, "OK", zoneObj[fieldName], "text/plain")

addUrl("/api/status/(?P<zoneId>.+)/(?P<fieldName>.+)$", urlApiGetZoneField)


def urlApiGetZoneAll(request):

    zoneId = request.pathDict['zoneId']
    if zoneId not in urlsystems.statusZones:
        return makeApiResponse(404, "No data", None)

    zoneObj = urlsystems.statusZones[zoneId]

    return makeApiResponse(200, "OK", json.dumps(zoneObj), "application/json")

addUrl("/api/status/(?P<zoneId>.+)$", urlApiGetZoneAll)



def urlApiGetZoneConfig(request):

    zoneId = request.pathDict['zoneId']
    if zoneId not in urlsystems.configZones:
        return makeApiResponse(404, "No data", None)

    zoneObj = urlsystems.configZones[zoneId]

    zoneObj["mode"] = urlsystems.currentMode
    zoneObj["units"] = urlsystems.tempUnits

    return makeApiResponse(200, "OK", json.dumps(zoneObj), "application/json")

addUrl("/api/config/(?P<zoneId>.+)$", urlApiGetZoneConfig)



def urlApiDeviceConfig(request):

    if urlsystems.configFromDevice == None:
        return makeApiResponse(200, "OK", None)
    else:
        return makeApiResponse(200, "OK", ET.tostring(urlsystems.configFromDevice, "utf-8"), "application/xml")

addUrl("/api/deviceConfig$", urlApiDeviceConfig)



def urlApiPendingActions(request):

    if urlsystems.pendingActionHold != None:
        return makeApiResponse(200, "OK", "yes", "text/plain")
    else:
        return makeApiResponse(200, "OK", "no", "text/plain")


addUrl("/api/pendingActions$", urlApiPendingActions)
