#
# /systems URL handling
#
# This module is the most complicated and where all of the interesting
# interaction with the thermostat happens.
#

import copy
from datetime import datetime
import logging
import json
import xmltodict
import xml.etree.ElementTree as ET
import requests


from .httpobj import HttpRequest, HttpResponse, addUrl

_LOGGER: logging.Logger = logging.getLogger(__package__)

# This is data shared between the API module and this one.  It lives here since
# the interaction with the thermostat is more critical than the API side and so
# these variables are tightly coupled with this module.
# The serial number of the thermostat
activeThermostatId = None
# Raw XML tree from the device's configuration last uploaded to us (../config
# URL).  Also required to send updated configuration since we will use the
# last known configuration and modify it as needed.
configFromDevice = None
configFromDeviceDict = {}
systemstatus = {}
# Parsed status of zones
statusZones = {}
# Parsed configuration of zones
configZones = {}
# Some parsed status of device for API module to use
currentMode = None
tempUnits = None
# The API module updates these variables for this module to use to send
# configuration changes to the device.  Once the configuration has been
# sent to the device (next time it polls for an update) these variables
# are reset back to None
pendingActionHold = None
pendingActionActivity = None
pendingActionTemp = None
pendingActionUntil = None

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
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
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
        pendingActionHold = True
        pendingActionActivity = None
        pendingActionTemp = None
        _LOGGER.info("Set pending hold=off")
        return makeApiResponse(200, "OK", None)

    if not activityValue or activityValue not in ("home", "away", "sleep", "wake", "manual"):
        _LOGGER.info("Bad activity value: %s", activityValue)
        return makeApiResponse(400, "Bad activity value", None)

    if untilValue:

        parts = untilValue.split(":")
        if len(parts) != 2 or len(parts[1]) != 2:
            _LOGGER.info("Bad until value: %s", untilValue)
            return makeApiResponse(400, "Bad until value", None)

        hourVal = int(parts[0])
        minuteVal = int(parts[1])

        if hourVal > 23 or hourVal < 0 or minuteVal > 59 or minuteVal < 0:
            _LOGGER.info("Bad until value: %s", untilValue)
            return makeApiResponse(400, "Bad until value", None)

        if minuteVal not in (0, 15, 30, 45):
            _LOGGER.info("until minute must be in 15 min increments: %s", untilValue)
            return makeApiResponse(400, "until minute must be in 15 min increments", None)

    else:

        if zoneId not in configZones:
            _LOGGER.info("Missing until value and no zone config")
            return makeApiResponse(400, "Missing until value and no zone config", None)

        zoneConfig = configZones[zoneId]

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
                _LOGGER.info("Missing until value and cannot find next activity")
                return makeApiResponse(400, "Missing until value and cannot find next activity", None)

        untilValue = activityEnd


    if activityValue == "manual":

        if not tempValue:
            _LOGGER.info("Missing temp value for manual")
            return makeApiResponse(400, "Missing temp value for manual", None)

        tempValue = float(tempValue)

        if tempValue < 16 or tempValue > 24:
            _LOGGER.info("temp value outside of range: %s", tempValue)
            return makeApiResponse(400, "temp value outside of range", None)

        testVal = tempValue * 2
        if not testVal.is_integer():
            _LOGGER.info("temp value must be in 0.5 increments: %s", tempValue)
            return makeApiResponse(400, "temp value must be 0.5 increments", None)

    pendingActionHold = True
    pendingActionActivity = activityValue
    pendingActionUntil = untilValue
    pendingActionTemp = tempValue

    _LOGGER.info("Set pending hold=on to {} until {} temp {}".format(pendingActionActivity, pendingActionUntil, pendingActionTemp))

    empty = {}
    return makeApiResponse(200, "OK", json.dumps(empty, sort_keys=True), "application/json")
addUrl("/api/hold/(?P<zoneId>.+)$", urlApiZoneSetHold)


def urlApiHold(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    zoneId = request.pathDict['zoneId']

    holdValue = False
    if "hold" in request.bodyDict:
        holdValue = request.bodyDict['hold'][0]

    activityValue = None
    if "holdActivity" in request.bodyDict:
        activityValue = request.bodyDict['holdActivity'][0]

    untilValue = None
    if "otmr" in request.bodyDict:
        untilValue = request.bodyDict['otmr'][0]

    tempValue = None
    if "temp" in request.bodyDict:
        tempValue = request.bodyDict['temp'][0]

    pendingActionHold = holdValue
    pendingActionActivity = activityValue
    pendingActionUntil = untilValue
    pendingActionTemp = tempValue

    _LOGGER.info("Set pending hold={} to {} until {} temp {}".format(holdValue, pendingActionActivity, pendingActionUntil, pendingActionTemp))
    empty = {}
    return makeApiResponse(200, "OK", json.dumps(empty, sort_keys=True), "application/json")
addUrl("/api/config/zones/zone/(?P<zoneId>.+)/$", urlApiHold)


def urlApiGetZoneField(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    zoneId = request.pathDict['zoneId']
    fieldName = request.pathDict['fieldName']

    if zoneId not in statusZones:
        return makeApiResponse(404, "No data", None)

    zoneObj = statusZones[zoneId]

    if fieldName not in zoneObj:
        return makeApiResponse(404, "No such field", None)

    return makeApiResponse(200, "OK", zoneObj[fieldName], "text/plain")
addUrl("/api/status/(?P<zoneId>.+)/(?P<fieldName>.+)$", urlApiGetZoneField)


def urlApiGetZoneAll(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    zoneId = request.pathDict['zoneId']
    if zoneId not in statusZones:
        return makeApiResponse(404, "No data", None)

    zoneObj = statusZones[zoneId]

    return makeApiResponse(200, "OK", json.dumps(zoneObj), "application/json")
addUrl("/api/status/(?P<zoneId>.+)$", urlApiGetZoneAll)

def urlApiGetZoneConfig(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    zoneId = request.pathDict['zoneId']
    if zoneId not in configZones:
        return makeApiResponse(404, "No data", None)

    zoneObj = configZones[zoneId]

    zoneObj["mode"] = currentMode
    zoneObj["units"] = tempUnits

    return makeApiResponse(200, "OK", json.dumps(zoneObj), "application/json")
addUrl("/api/config/(?P<zoneId>.+)$", urlApiGetZoneConfig)

def urlApiDeviceConfig(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    if configFromDevice == None:
        return makeApiResponse(200, "OK", None)
    else:
        return makeApiResponse(200, "OK", ET.tostring(configFromDevice, "utf-8"), "application/xml")
addUrl("/api/deviceConfig$", urlApiDeviceConfig)


def urlApiConfig(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    empty = {}
    if configFromDeviceDict == None:
        return makeApiResponse(200, "OK", json.dumps(empty, sort_keys=True), "application/json")
    else:
        return makeApiResponse(200, "OK", json.dumps(configFromDeviceDict["system"], sort_keys=True), "application/json")
addUrl("/api/config", urlApiConfig)

def urlApiStatus(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    empty = {}
    if systemstatus == None:
        return makeApiResponse(200, "OK", json.dumps(empty,sort_keys=True), "application/json")
    else:
        return makeApiResponse(200, "OK", json.dumps(systemstatus["status"],sort_keys=True), "application/json")
addUrl("/api/status", urlApiStatus)

def urlApiPendingActions(request):
    global activeThermostatId
    global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
    global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
    if pendingActionHold != None:
        return makeApiResponse(200, "OK", "yes", "text/plain")
    else:
        return makeApiResponse(200, "OK", "no", "text/plain")
addUrl("/api/pendingActions", urlApiPendingActions)


#========================================================================================================
#========================================================================================================
#========================================================================================================
#========================================================================================================
#========================================================================================================
#========================================================================================================
#========================================================================================================
#========================================================================================================

# Information about the device (serial numbers and modules) but not
# current configuration.
def urlSystemsProfile(request):

	xmlBodyStr = request.bodyDict["data"][0]

	#_LOGGER.debug("  SN={}".format(request.pathDict["serialNumber"]))
	_LOGGER.info("  body={}".format(xmlBodyStr))

	response = HttpResponse.okResponse()

	response.headers.append(("Cache-Control", "private"))
	response.addServerHeader()
	response.addRequestContextHeader()
	response.addAccessControlHeader()
	response.addDateHeader()
	response.addContentLengthHeader(0)

	return response
addUrl("/systems/(?P<serialNumber>.+)/profile$", urlSystemsProfile)



# Device tells us the dealer information that has been programmed into the
# device.  (We do not send back any information.)
def urlSystemsDealer(request):

    xmlBodyStr = request.bodyDict["data"][0]

    #_LOGGER.debug("  SN={}".format(request.pathDict["serialNumber"]))
    _LOGGER.info("  body={}".format(xmlBodyStr))

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "private"))
    response.headers.append(("Etag", "\"00f5713108d7b88afec10590\""))
    response.addServerHeader()
    response.addRequestContextHeader()
    response.addAccessControlHeader()
    response.addDateHeader()
    response.addContentLengthHeader(0)

    return response
addUrl("/systems/(?P<serialNumber>.+)/dealer$", urlSystemsDealer)



# Device tells us about its internal furance devices (built-in heating?)
def urlSystemsIDUConfig(request):

    xmlBodyStr = request.bodyDict["data"][0]

    #_LOGGER.debug("  SN={}".format(request.pathDict["serialNumber"]))
    _LOGGER.info("  body={}".format(xmlBodyStr))

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "private"))
    response.headers.append(("Etag", "\"0357dfbd08d7b88aff27ec1e\""))
    response.addServerHeader()
    response.addRequestContextHeader()
    response.addAccessControlHeader()
    response.addDateHeader()
    response.addContentLengthHeader(0)

    return response
addUrl("/systems/(?P<serialNumber>.+)/idu_config$", urlSystemsIDUConfig)

def urlSystemsidu_faults(request):

	#_LOGGER.info("  SN={}".format(request.pathDict["serialNumber"]))
	xmlStringData = request.bodyDict["data"][0]
	_LOGGER.info("  idu_faults={}".format(xmlStringData))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/idu_faults$", urlSystemsidu_faults)

# Device tells us about its internal furance devices (built-in heating?)
def urlSystemsIDUStatus(request):

	xmlBodyStr = request.bodyDict["data"][0]

	#_LOGGER.debug("  SN={}".format(request.pathDict["serialNumber"]))
	_LOGGER.info("  body={}".format(xmlBodyStr))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/idu_status$", urlSystemsIDUStatus)


# Device tells us about its external furnace devices (air conditioning? secondary
# heating or cooling systems?)
def urlSystemsODUConfig(request):

    xmlBodyStr = request.bodyDict["data"][0]

    #_LOGGER.debug("  SN={}".format(request.pathDict["serialNumber"]))
    _LOGGER.info("  body={}".format(xmlBodyStr))

    response = HttpResponse.okResponse()

    response.headers.append(("Cache-Control", "private"))
    response.headers.append(("Etag", "\"039f3ffe08d7b88aff98b843\""))
    response.addServerHeader()
    response.addRequestContextHeader()
    response.addAccessControlHeader()
    response.addDateHeader()
    response.addContentLengthHeader(0)

    return response
addUrl("/systems/(?P<serialNumber>.+)/odu_config$", urlSystemsODUConfig)

def urlSystemsodu_faults(request):

	#_LOGGER.info("  SN={}".format(request.pathDict["serialNumber"]))
	xmlStringData = request.bodyDict["data"][0]
	_LOGGER.info("  odu_faults={}".format(xmlStringData))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/odu_faults$", urlSystemsodu_faults)

# Device tells us about its internal furance devices (built-in heating?)
def urlSystemsODUStatus(request):

	xmlBodyStr = request.bodyDict["data"][0]

	#_LOGGER.debug("  SN={}".format(request.pathDict["serialNumber"]))
	_LOGGER.info("  body={}".format(xmlBodyStr))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/odu_status$", urlSystemsODUStatus)



# Device tells us current status, such as temperature, humidity, current
# schedule activity, temp set points, and if it is running.  We can respond
# with a list of booleans to ask the device to make another /systems call
# soon, such as to download updated configuration.  We can also adjust the
# rate at which it polls for the various /systems calls here.
def makeSystemsStatusResponse(request, serverHasChanges, configHasChanges):

	serialNumber = request.pathDict["serialNumber"]

	statusRoot = ET.Element("status")

	statusRoot.set("version", "1.42")
	statusRoot.set("xmlns:atom", "http://www.w3.org/2005/Atom")

	atomLink = ET.Element("atom:link")
	atomLink.set("rel", "self")
	atomLink.set("href", "http://www.api.ing.carrier.com/systems/" + serialNumber + "/status")
	statusRoot.append(atomLink)

	atomLink = ET.Element("atom:link")
	atomLink.set("rel", "http://www.api.ing.carrier.com/rels/system")
	atomLink.set("href", "http://www.api.ing.carrier.com/systems/" + serialNumber)
	statusRoot.append(atomLink)

	tsEl = ET.Element("timestamp")
	tsEl.text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
	statusRoot.append(tsEl)

	el = ET.Element("pingRate")
	el.text = "30"
	statusRoot.append(el)

	el = ET.Element("iduStatusPingRate")
	el.text = "93600"
	statusRoot.append(el)

	el = ET.Element("iduFaultsPingRate")
	el.text = "86400"
	statusRoot.append(el)

	el = ET.Element("oduStatusPingRate")
	el.text = "90000"
	statusRoot.append(el)

	el = ET.Element("oduFaultsPingRate")
	el.text = "82800"
	statusRoot.append(el)

	el = ET.Element("historyPingRate")
	el.text = "75600"
	statusRoot.append(el)

	el = ET.Element("equipEventsPingRate")
	el.text = "79200"
	statusRoot.append(el)

	el = ET.Element("rootCausePingRate")
	el.text = "72000"
	statusRoot.append(el)

	el = ET.Element("serverHasChanges")
	if serverHasChanges:
		el.text = "true"
	else:
		el.text = "false"
	statusRoot.append(el)

	el = ET.Element("configHasChanges")
	if configHasChanges:
		el.text = "true"
	else:
		el.text = "false"
	statusRoot.append(el)

	el = ET.Element("dealerHasChanges")
	el.text = "false"
	statusRoot.append(el)

	el = ET.Element("dealerLogoHasChanges")
	el.text = "false"
	statusRoot.append(el)

	el = ET.Element("oduConfigHasChanges")
	el.text = "false"
	statusRoot.append(el)

	el = ET.Element("iduConfigHasChanges")
	el.text = "false"
	statusRoot.append(el)

	el = ET.Element("utilityEventsHasChanges")
	el.text = "false"
	statusRoot.append(el)

	el = ET.Element("sensorConfigHasChanges")
	el.text = "false"
	statusRoot.append(el)

	el = ET.Element("sensorProfileHasChanges")
	el.text = "false"
	statusRoot.append(el)

	el = ET.Element("sensorDiagnosticHasChanges")
	el.text = "false"
	statusRoot.append(el)

	xmlBodyStr = ET.tostring(statusRoot, "utf-8")

	response = HttpResponse.okResponse()

	response.headers.append(("Cache-Control", "private"))
	response.addContentLengthHeader(len(xmlBodyStr))
	response.addContentTypeHeader("application/xml; charset=utf-8")
	response.addServerHeader()
	response.addRequestContextHeader()
	response.addAccessControlHeader()
	response.addDateHeader()

	response.body = xmlBodyStr

	return response


def urlSystemsStatus(request):
	global activeThermostatId
	global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
	global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
	xmlStringData = request.bodyDict["data"][0]

	#_LOGGER.debug("  SN={}".format(request.pathDict["serialNumber"]))

	xmlRoot = ET.fromstring(xmlStringData)

	if xmlRoot.attrib['version'] != "1.7":
		_LOGGER.warning("Unexpected client version: %s" % (xmlRoot.attrib['version'], ))
		return makeSystemsStatusResponse(request, False, False)

	currentMode = xmlRoot.find("./cfgtype").text
	tempUnits = xmlRoot.find("./cfgem").text

	systemstatus = xmltodict.parse(xmlStringData)

	statusZones = {}

	for zone in xmlRoot.findall("./zones/zone"):

		if zone.find("./enabled").text != "on":
			continue

		zoneId = zone.attrib['id']

		zoneObj = {
			"name": zone.find("./name").text,
			"activity": zone.find("./currentActivity").text,
			"temperature": zone.find("./rt").text,
			"humidity": zone.find("./rh").text,
			"heatTo": zone.find("./htsp").text,
			"coolTo": zone.find("./clsp").text,
			"fan": zone.find("./fan").text,
			"hold": zone.find("./hold").text,
			"until" : zone.find("./otmr").text,
			"zoneConditioning" : zone.find("./zoneconditioning").text
		}

		statusZones[zoneId] = zoneObj



	if pendingActionHold:
		_LOGGER.info("Returned has status changes")
		response = makeSystemsStatusResponse(request, True, True)
	elif not configFromDevice:
		_LOGGER.info("Returned want config")
		response = makeSystemsStatusResponse(request, True, True)
	else:
		_LOGGER.debug("Returned NO status changes")
		response = makeSystemsStatusResponse(request, False, False)

	return response
addUrl("/systems/(?P<serialNumber>.+)/status$", urlSystemsStatus)



# I don't have utility events set up in the themostat to test this.
def urlSystemsUtilityEvents(request):

	#_LOGGER.info("  SN={}".format(request.pathDict["serialNumber"]))
	#xmlStringData = request.bodyDict["data"][0]
	#_LOGGER.info("  UtilEvents={}".format(xmlStringData))

	utilityXMLStr = '<utility_events version="1.42" xmlns:atom="http://www.w3.org/2005/Atom"/>'

	response = HttpResponse.okResponse()

	response.headers.append(("Cache-Control", "private"))
	response.addContentLengthHeader(len(utilityXMLStr))
	response.addContentTypeHeader("application/xml; charset=utf-8")
	response.addServerHeader()
	response.addRequestContextHeader()
	response.addAccessControlHeader()
	response.addDateHeader()

	response.body = utilityXMLStr

	return response
addUrl("/systems/(?P<serialNumber>.+)/utility_events$", urlSystemsUtilityEvents)

def urlSystemsEquipment_Events(request):

	#_LOGGER.info("  SN={}".format(request.pathDict["serialNumber"]))
	xmlStringData = request.bodyDict["data"][0]
	_LOGGER.info("  Equipment_Events={}".format(xmlStringData))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/equipment_events$", urlSystemsEquipment_Events)

def urlSystemsroot_cause(request):

	#_LOGGER.info("  SN={}".format(request.pathDict["serialNumber"]))
	xmlStringData = request.bodyDict["data"][0]
	_LOGGER.info("  root_cause={}".format(xmlStringData))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/root_cause$", urlSystemsroot_cause)

def urlSystemsequipment_events(request):

	#_LOGGER.info("  SN={}".format(request.pathDict["serialNumber"]))
	xmlStringData = request.bodyDict["data"][0]
	_LOGGER.info("  equipment_events={}".format(xmlStringData))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/equipment_events$", urlSystemsequipment_events)


def urlSystemsEnergy(request):

	xmlStringData = request.bodyDict["data"][0]
	_LOGGER.info("  Energy={}".format(xmlStringData))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/energy$", urlSystemsEnergy)


def urlSystemsHistory(request):

	xmlStringData = request.bodyDict["data"][0]
	_LOGGER.info("  History={}".format(xmlStringData))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/history$", urlSystemsHistory)



# The device tells us when it has made a change such as appling a new
# configuration.  This both confirms a configuration change that we may have
# requested in the .../config response, but also if a person changes the config
# on the thermostat's touch screen.
def makeSimpleXMLResponse():

	response = HttpResponse.okResponse()

	response.headers.append(("Cache-Control", "private"))
	response.addContentTypeHeader("application/xml; charset=utf-8")
	response.addServerHeader()
	response.addRequestContextHeader()
	response.addAccessControlHeader()
	response.addDateHeader()
	response.addContentLengthHeader(0)

	return response


def urlSystemsNotifications(request):

	xmlStringData = request.bodyDict["data"][0]

	_LOGGER.info("  SN={}".format(request.pathDict["serialNumber"]))

	xmlRoot = ET.fromstring(xmlStringData)

	if xmlRoot.attrib['version'] != "1.7":
		_LOGGER.warning("Unexpected client version: %s" % (xmlRoot.attrib['version'], ))
		return makeSimpleXMLResponse()

	responseCode = xmlRoot.find("./notification/code").text
	responseMessage = xmlRoot.find("./notification/message").text

	if responseCode != "200":
		_LOGGER.warning("Thermostat responded with code: %s, message %s" % (responseCode, responseMessage))
		return makeSimpleXMLResponse()

	# Save for api access?

	_LOGGER.info("Thermostat notification: %s %s" % (responseCode, responseMessage))

	return makeSimpleXMLResponse()
addUrl("/systems/(?P<serialNumber>.+)/notifications$", urlSystemsNotifications)



# The device is requesting an updated configuration from us.
def makeSystemsConfigResponse(xmlBodyStr):

	response = HttpResponse.okResponse()

	response.headers.append(("Cache-Control", "private"))
	response.addContentLengthHeader(len(xmlBodyStr))
	response.addContentTypeHeader("application/xml; charset=utf-8")
	response.headers.append(("Etag", "\"00de388808d7b88cd8f146a1\""))
	response.addServerHeader()
	response.addRequestContextHeader()
	response.addAccessControlHeader()
	response.addDateHeader()

	response.body = xmlBodyStr

	return response


def urlSystemsConfig(request):
	global activeThermostatId
	global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
	global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
	serialNumber = request.pathDict["serialNumber"]

	_LOGGER.debug("  SN={}".format(serialNumber))

	# Can't return config unless we know what the device is already using
	if configFromDevice == None:
		return makeSystemsConfigResponse("")

	newConfigRoot = copy.deepcopy(configFromDevice)

	newConfigRoot.set("version", "1.42")
	newConfigRoot.set("xmlns:atom", "http://www.w3.org/2005/Atom")

	tsEl = ET.Element("timestamp")
	tsEl.text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
	newConfigRoot.insert(0, tsEl)

	atomLink = ET.Element("atom:link")
	atomLink.set("rel", "http://www.api.ing.carrier.com/rels/system")
	atomLink.set("href", "http://www.api.ing.carrier.com/systems/" + serialNumber)
	newConfigRoot.insert(0, atomLink)

	atomLink = ET.Element("atom:link")
	atomLink.set("rel", "self")
	atomLink.set("href", "http://www.api.ing.carrier.com/systems/" + serialNumber + "/config")
	newConfigRoot.insert(0, atomLink)

	for zone in newConfigRoot.findall("./zones/zone"):

		if zone.find("./enabled").text != "on":
			continue

		if zone.attrib['id'] != "1":
			continue

		if pendingActionHold:
			if pendingActionActivity:
				zone.find("./hold").text = "on"
				zone.find("./holdActivity").text = pendingActionActivity
				zone.find("./otmr").text = pendingActionUntil
			else:
				zone.find("./hold").text = "off"
				zone.find("./holdActivity").text = ""
				zone.find("./otmr").text = ""

			if pendingActionActivity == "manual":
				for activity in zone.findall("./activities/activity"):

					if activity.attrib['id'] != "manual":
						continue

					activity.find("./htsp").text = str(pendingActionTemp)

	pendingActionHold = None
	pendingActionActivity = None
	pendingActionUntil = None
	pendingActionTemp = None

	xmlDataStr = ET.tostring(newConfigRoot, "utf-8")
	return makeSystemsConfigResponse(xmlDataStr)
addUrl("/systems/(?P<serialNumber>.+)/config$", urlSystemsConfig)



# The device is telling us about root causes of something?
def makeSystemsRootCauseResponse():

	response = HttpResponse.errorResponse(404, "Not found")
	#response = HttpResponse.okResponse()

	#response.headers.append(("Cache-Control", "private"))
	#response.addContentTypeHeader("application/xml; charset=utf-8")
	#response.addServerHeader()
	#response.addRequestContextHeader()
	#response.addAccessControlHeader()
	#response.addDateHeader()
	#response.addContentLengthHeader(0)

	return response


def urlSystemsRootCause(request):

	xmlStringData = request.bodyDict["data"][0]

	_LOGGER.info("Root Cause {}".format(xmlStringData))

	return makeSystemsRootCauseResponse()
addUrl("/systems/(?P<serialNumber>.+)/root_cause$", urlSystemsRootCause)


# The device is telling us about its configuration.  It appears that just about
# anything that can be controlled on the touch screen will be included here,
# including the full activity schedule, and what devices are attached (gas, A/C,
# etc).
def makeSystemsResponse():

	response = HttpResponse.okResponse()

	response.headers.append(("Cache-Control", "private"))
	response.headers.append(("Etag", "\"0180958508d7b88afdc6a55c\""))
	response.addServerHeader()
	response.addRequestContextHeader()
	response.addAccessControlHeader()
	response.addDateHeader()
	response.addContentLengthHeader(0)

	return response

def urlsystems(request):
	global activeThermostatId
	global configFromDevice, configFromDeviceDict, systemstatus, statusZones, configZones, currentMode, tempUnits
	global pendingActionHold, pendingActionActivity, pendingActionTemp, pendingActionUntil
	serialNumber = request.pathDict["serialNumber"]
	xmlStringData = request.bodyDict["data"][0]

	_LOGGER.debug("  SN={}".format(serialNumber))
	_LOGGER.info("  body={}".format(xmlStringData))

	xmlRoot = ET.fromstring(xmlStringData)

	if xmlRoot.attrib['version'] != "1.7":
		_LOGGER.warning("Unexpected client version: %s" % (xmlRoot.attrib['version'], ))
		return makeSystemsResponse()

	currentMode = xmlRoot.find("./config/mode").text
	tempUnits = xmlRoot.find("./config/cfgem").text

	activeThermostatId = serialNumber
	configFromDevice = xmlRoot.find("./config")
	configFromDeviceDict = xmltodict.parse(xmlStringData)
	
	configZones = {}

	for zone in xmlRoot.findall("./config/zones/zone"):

		zoneId = zone.attrib['id']

		configZoneObj = {
			"activities": {},
			"schedule": {}
		}

		for activity in zone.findall("./activities/activity"):

			activityId = activity.attrib['id']

			activityObj = {
				"heatTo": activity.find("./htsp").text,
				"coolTo": activity.find("./clsp").text,
				"fan": activity.find("./fan").text
			}

			configZoneObj["activities"][activityId] = activityObj

		for day in zone.findall("./program/day"):

			dayId = day.attrib['id']

			periodList = {}

			for period in day.findall("./period"):

				periodId = int(period.attrib['id'])

				periodObj = {
					"activity": period.find("./activity").text,
					"time": period.find("./time").text,
					"enabled": period.find("./enabled").text == "on"
				}

				periodList[periodId] = periodObj

			configZoneObj["schedule"][dayId] = periodList

		configZones[zoneId] = configZoneObj


	return makeSystemsResponse()
addUrl("/systems/(?P<serialNumber>[^/]+)$", urlsystems)
