from astropy.coordinates import SkyCoord, EarthLocation, get_body
import numpy as np
import matplotlib.pyplot as plt
import astroplan as apl
import astropy.units as u
from astropy.time import Time
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo
import datetime

night_colors = [
    "#cce5ff",
    "#99ccff",
    "#4d88ff",
    "#1a1aff",
    "#4d88ff",
    "#99ccff",
    "#cce5ff",
]

moon_color = "#b386ff"

def observation_time_to_UTC_offset(observatory):

    lat, lon = EarthLocation.of_site(observatory).lat.deg, EarthLocation.of_site(observatory).lon.deg
    tz = TimezoneFinder().timezone_at(lat=lat, lng=lon)
    offset = datetime.datetime.now().replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo(tz)).utcoffset().total_seconds() // 3600
    
    return offset

def observation_time(observatory, date):
    
    offset = observation_time_to_UTC_offset(observatory)
    obs_time = Time(date, scale='utc') + np.linspace(-12, 12, 4 * 24) * u.hour

    return obs_time

def target_coordinates(ra, dec, observatory, obs_time):
    
    target = SkyCoord(ra=ra*u.deg, dec=dec*u.deg, frame='icrs')
    observer = apl.Observer.at_site(observatory)
    coordinates = observer.altaz(obs_time, target=target)

    return coordinates

def moon_coordinates(observatory, obs_time):
    
    observer = apl.Observer.at_site(observatory)
    coordinates = observer.moon_altaz(obs_time)

    return coordinates

def from_elevation_to_airmass(elevation):
    return 1 / np.cos(np.radians(90 - elevation))

def get_moon_phase(time):

    # Moon angle of illumination
    phase_angle = apl.moon_phase_angle(time).value  * 180 / np.pi
    elongation = get_body('moon', time).ra - get_body('sun', time).ra
    if elongation < 0:
        elongation += 360 * u.deg

    # New Moon
    if phase_angle > 170:
        return '\U0001F311'

    # Full Moon
    elif phase_angle < 10:
        return '\U0001F315'

    else:
        # Waxing Moon
        if elongation.value < 180 :
            # Waxing Crescent
            if phase_angle >= 100:
                return '\U0001F312'

            # First Quarter
            elif phase_angle > 80:
                return '\U0001F313'

            # Waxing Gibbous
            else:
                return '\U0001F314'

        # Waning Moon
        else:
            # Waning Gibbous
            if phase_angle <= 80:
                return '\U0001F316'

            # Last Quarter
            elif phase_angle < 100:
                return '\U0001F317'
                
            # Waning Crescent
            else:
                return '\U0001F318'

def get_moon_illumination(time):
    return apl.moon_illumination(time)

def UTC_night_hours(observatory, date, offset):
    observer = apl.Observer.at_site(observatory)
    twilights = {
        'Sunset': observer.sun_set_time(Time(date) - offset * u.hour, which='previous') + offset * u.hour,
        'Civil twilight': observer.twilight_evening_civil(Time(date) - offset * u.hour, which='previous') + offset * u.hour,
        'Nautical twilight': observer.twilight_evening_nautical(Time(date) - offset * u.hour, which='previous') + offset * u.hour,
        'Astronomical twilight': observer.twilight_evening_astronomical(Time(date) - offset * u.hour, which='previous') + offset * u.hour,
        'Astronomical morning': observer.twilight_morning_astronomical(Time(date) - offset * u.hour, which='next') + offset * u.hour,
        'Nautical morning': observer.twilight_morning_nautical(Time(date) - offset * u.hour, which='next') + offset * u.hour,
        'Civil morning': observer.twilight_morning_civil(Time(date) - offset * u.hour, which='next') + offset * u.hour,
        'Sunrise': observer.sun_rise_time(Time(date) - offset * u.hour, which='next') + offset * u.hour,
    }
    return twilights
