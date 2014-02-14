"""
This library/script will grab a web page from thetvdb.com and use
the TV network info in the SELECT OPTIONs to make a lookup table
that can be used to determine what country a show is broadcast in.
"""
import re, urllib

# This holds the hour offset (e.g. -3.5) and True if they change for DST
COUNTRY_ZONES = {
    'argentina': (-3, True),
    'australia': (10, True),
    'austria': (1, True),
    'belgium': (1, True),
    'brazil': (-3, True),
    'bulgaria': (2, True),
    'canada': (-4, True),
    'chile': (-4, True),
    'china': (8, True),
    'colombia': (-5, True),
    'croatia': (1, True),
    'czech republic': (1, True),
    'denmark': (1, True),
    'finland': (2, True),
    'france': (1, True),
    'germany': (1, True),
    'greece': (2, True),
    'hong kong': (8, True),
    'hungary': (1, True),
    'india': (5.5, True),
    'indonesia': (9, True),
    'iran': (3.5, True),
    'ireland': (0, True),
    'israel': (2, True),
    'italy': (1, True),
    'japan': (9, True),
    'luxembourg': (1, True),
    'malaysia': (8, True),
    'malta': (1, True),
    'mexico': (-6, True),
    'monaco': (1, True),
    'netherlands': (1, True),
    'new zealand': (12, True),
    'nigeria': (1, True),
    'north korea': (9, True),
    'norway': (1, True),
    'pakistan': (5, True),
    'philippines': (8, True),
    'poland': (1, True),
    'portugal': (0, True),
    'qatar': (3, True),
    'romania': (2, True),
    'russia': (12, True),
    'singapore': (8, True),
    'south africa': (2, True),
    'south korea': (9, True),
    'spain': (1, True),
    'sri lanka': (5.5, True),
    'sweden': (1, True),
    'switzerland': (1, True),
    'taiwan': (8, True),
    'turkey': (2, True),
    'ukraine': (2, True),
    'united arab emirates': (4, True),
    'united kingdom': (0, True),
    'united states': (-5, True),
    'uruguay': (-3, True),
    'venezuela': (4.5, True),
    'unknown': (1, False),
};

class CountryLookup(object):
    def __init__(self, series_id = 70386):
        url = 'http://thetvdb.com/?tab=series&id=%d&lid=7' % series_id

        sel_re = re.compile(r'<select.*name="changenetwork"')
        opt_re = re.compile(r'<option.*value="(.*?)">[^<]+\((.*?)\)')

        self.country_dict = {}
        in_select = False
        saw_data = False

        data = urllib.urlopen(url)
        for line in data:
            if in_select:
                m = opt_re.search(line)
                if m:
                    self.country_dict[m.group(1)] = m.group(2)
                    saw_data = True
                elif saw_data:
                    break
            elif sel_re.search(line):
                in_select = True

        self.country_dict[''] = 'Unknown'

    def get_country_dict(self):
        return self.country_dict

    # If this returns None and you want our default tzone, call back with country "Unknown".
    @staticmethod
    def get_country_timezone(country, in_dst):
        adjust, follows_dst = COUNTRY_ZONES.get(country.lower(), (None, False))
        if adjust is None:
            return None
        if follows_dst and in_dst:
            adjust += 1
        plus_minus = '-' if adjust < 0 else '+'
        return '%s%02d:%02d' % (plus_minus, abs(int(adjust)), (adjust*60) - (int(adjust)*60))

if (__name__ == "__main__"):
    c = CountryLookup()
    print repr(c.get_country_dict()).replace('), ', "),\n")

# vim: et
