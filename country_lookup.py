"""
This library/script will grab a web page from thetvdb.com and use
the TV network info in the SELECT OPTIONs to make a lookup table
that can be used to determine what country a show is broadcast in.
"""
import re, urllib

COUNTRY_ZONES = {
    'argentina': '-03:00',
    'australia': '+10:00',
    'austria': '+01:00',
    'belgium': '+01:00',
    'brazil': '-03:00',
    'bulgaria': '+02:00',
    'canada': '-04:00',
    'chile': '-04:00',
    'china': '+08:00',
    'colombia': '-05:00',
    'croatia': '+01:00',
    'czech republic': '+01:00',
    'denmark': '+01:00',
    'finland': '+02:00',
    'france': '+01:00',
    'germany': '+01:00',
    'greece': '+02:00',
    'hong kong': '+08:00',
    'hungary': '+01:00',
    'india': '+05:30',
    'indonesia': '+09:00',
    'iran': '+03:30',
    'ireland': '+00:00',
    'israel': '+02:00',
    'italy': '+01:00',
    'japan': '+09:00',
    'luxembourg': '+01:00',
    'malaysia': '+08:00',
    'malta': '+01:00',
    'mexico': '-06:00',
    'monaco': '+01:00',
    'netherlands': '+01:00',
    'new zealand': '+12:00',
    'nigeria': '+01:00',
    'north korea': '+09:00',
    'norway': '+01:00',
    'pakistan': '+05:00',
    'philippines': '+08:00',
    'poland': '+01:00',
    'portugal': '+00:00',
    'qatar': '+03:00',
    'romania': '+02:00',
    'russia': '+12:00',
    'singapore': '+08:00',
    'south africa': '+02:00',
    'south korea': '+09:00',
    'spain': '+01:00',
    'sri lanka': '+05:30',
    'sweden': '+01:00',
    'switzerland': '+01:00',
    'taiwan': '+08:00',
    'turkey': '+02:00',
    'ukraine': '+02:00',
    'united arab emirates': '+04:00',
    'united kingdom': '+00:00',
    'united states': '-05:00',
    'uruguay': '-03:00',
    'venezuela': '+04:30',
    'unknown': '+01:00',
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
    def get_country_timezone(country):
        return COUNTRY_ZONES.get(country.lower(), None)

if (__name__ == "__main__"):
    c = CountryLookup()
    print repr(c.get_country_dict()).replace('), ', "),\n")

# vim: et
