import urllib2
from math import cos
from math import radians
from json import loads

def clamp(n, low, high):
    """ensure that a number n is constrained in a range"""
    return min(high, max(low, n))

def latlon_bbox(lat, lon, d):
    """
    calculates a latlon bbox given a lat/lon and a distance d in miles
    """
    APPROX_MILES_PER_DEGREE = 69
    lon1 = lon - d / abs(cos(radians(lat)) * APPROX_MILES_PER_DEGREE)
    lon2 = lon + d / abs(cos(radians(lat)) * APPROX_MILES_PER_DEGREE)
    lat1 = lat - (d / APPROX_MILES_PER_DEGREE)
    lat2 = lat + (d / APPROX_MILES_PER_DEGREE)
    return (lat1, lat2, lon1, lon2)

def zipcode_to_latlon(zipcode):
    """looks up the zip code to determine the lat/lon"""
    url = 'http://maps.googleapis.com/maps/api/geocode/json?sensor=false&address=%s' % zipcode
    response = urllib2.urlopen(url)
    response_data = response.read()
    try:
        json_result = loads(response_data)
    except ValueError:
        return None
    if json_result.get('status', '') != 'OK':
        return None
    locations = json_result.get('results', [])
    if locations:
        latlng_map = locations[0].get('geometry', {}).get('location', {})
        lat = latlng_map.get('lat')
        lon = latlng_map.get('lng')
        if lat is not None and lon is not None:
            return (lat, lon)
    return None
