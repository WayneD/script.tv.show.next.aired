"""
thetvdb.com Python API
(c) 2009 James Smith (http://loopj.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import urllib
import datetime
import random
import re
import copy

import xml.etree.ElementTree as ET
import xml.parsers.expat as expat
from cStringIO import StringIO
from zipfile import ZipFile

class TheTVDB(object):
    def __init__(self, api_key='2B8557E0CBF7D720', language = 'en'):
        #http://thetvdb.com/api/<apikey>/<request>
        self.api_key = api_key
        self.mirror_url = "http://thetvdb.com"
        self.base_url =  self.mirror_url + "/api"
        self.base_key_url = "%s/%s" % (self.base_url, self.api_key)
        self.language = language

        self.select_mirrors()

    def select_mirrors(self):
        #http://thetvdb.com/api/<apikey>/mirrors.xml
        url = "%s/mirrors.xml" % self.base_key_url
        data = urllib.urlopen(url)
        try:
            tree = ET.parse(data)
            self.xml_mirrors = []
            self.zip_mirrors = []
            for mirror in tree.getiterator("Mirror"):
                mirrorpath = mirror.findtext("mirrorpath")
                typemask = mirror.findtext("typemask")
                if not mirrorpath or not typemask:
                    continue
                typemask = int(typemask)
                if typemask & 1:
                    self.xml_mirrors.append(mirrorpath)
                if typemask & 4:
                    self.zip_mirrors.append(mirrorpath)
        except SyntaxError:
            self.xml_mirrors = self.zip_mirrors = []

        if not self.xml_mirrors:
            self.xml_mirrors = [ self.mirror_url ]
        if not self.zip_mirrors:
            self.zip_mirrors = [ self.mirror_url ]

        self.xml_mirror_url = random.choice(self.xml_mirrors)
        self.zip_mirror_url = random.choice(self.zip_mirrors)

        self.base_xml_url = "%s/api/%s" % (self.xml_mirror_url, self.api_key)
        self.base_zip_url = "%s/api/%s" % (self.zip_mirror_url, self.api_key)

    @staticmethod
    def convert_time(time_string):
        """Convert a thetvdb time string into a datetime.time object."""
        time_res = [re.compile(r"\D*(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?.*(?P<ampm>a|p)m.*", re.IGNORECASE), # 12 hour
                    re.compile(r"\D*(?P<hour>\d{1,2}):?(?P<minute>\d{2}).*")]                                     # 24 hour

        for r in time_res:
            m = r.match(time_string)
            if m:
                gd = m.groupdict()

                if "hour" in gd and "minute" in gd and gd["minute"] and "ampm" in gd:
                    hour = int(gd["hour"])
                    if hour == 12:
                        hour = 0
                    if gd["ampm"].lower() == "p":
                        hour += 12

                    return datetime.time(hour, int(gd["minute"]))
                elif "hour" in gd and "ampm" in gd:
                    hour = int(gd["hour"])
                    if hour == 12:
                        hour = 0
                    if gd["ampm"].lower() == "p":
                        hour += 12

                    return datetime.time(hour, 0)
                elif "hour" in gd and "minute" in gd:
                    return datetime.time(int(gd["hour"]), int(gd["minute"]))

        return None

    @staticmethod
    def convert_date(date_string):
        """Convert a thetvdb date string into a datetime.date object."""
        first_aired = None
        try:
            first_aired = datetime.date(*map(int, date_string.split("-")))
        except ValueError:
            pass

        return first_aired

    def get_matching_shows(self, show_name):
        """Get a list of shows matching show_name."""
        get_args = urllib.urlencode({"seriesname": show_name}, doseq=True)
        url = "%s/GetSeries.php?%s" % (self.base_url, get_args)
        data = urllib.urlopen(url)
        show_list = []
        try:
            tree = ET.parse(data)
            show_list = [(show.findtext("seriesid"), show.findtext("SeriesName"),show.findtext("IMDB_ID")) for show in tree.getiterator("Series")]
        except SyntaxError:
            pass

        return show_list

    def get_show(self, show_id):
        """Get the show object matching this show_id."""
        #url = "%s/series/%s/%s.xml" % (self.base_key_url, show_id, "el")
        url = "%s/series/%s/" % (self.base_xml_url, show_id)
        show, eps = self.get_show_and_or_eps(url)
        return show

    def get_episode(self, episode_id):
        """Get the episode object matching this episode_id."""
        url = "%s/episodes/%s" % (self.base_xml_url, episode_id)
        show, eps = self.get_show_and_or_eps(url)
        return eps[0] if eps else None

    def get_show_and_episodes(self, show_id, atleast = 1):
        """Get the show object and all matching episode objects for this show_id."""
        url = "%s/series/%s/all/%s.zip" % (self.base_zip_url, show_id, self.language)
        zip_name = '%s.xml' % self.language
        show, eps = self.get_show_and_or_eps(url, zip_name, atleast)
        return (show, eps) if show else None

    def get_show_and_or_eps(self, url, zip_name = None, atleast = 1):
        data = urllib.urlopen(url)
        if zip_name:
            try:
                zipfile = ZipFile(StringIO(data.read()))
                data = zipfile.open(zip_name)
            except:
                return None

        self.show_tmp = None
        self.episodes_tmp = []
        self.epid_atleast = atleast
        e = ExpatParseXml(self.show_and_ep_callback)
        try:
            e.parse(data)
        except expat.ExpatError:
            print "Failed to get parsable XML for %s" % url

        show_and_episodes = (self.show_tmp, self.episodes_tmp)
        self.show_tmp = self.episodes_tmp = None
        return show_and_episodes

    def show_and_ep_callback(self, name, attrs):
        if name == 'Episode':
            if int(attrs['id']) >= self.epid_atleast:
                self.episodes_tmp.append(attrs)
        elif name == 'Series':
            self.show_tmp = attrs

    def get_update_filehandle(self, period):
        url = "%s/updates/updates_%s.zip" % (self.base_zip_url, period)
        data = urllib.urlopen(url)
        fh = None
        try:
            zipfile = ZipFile(StringIO(data.read()))
            want_name = 'updates_%s.xml' % period
            fh = zipfile.open(want_name)
        except:
            pass

        return fh

    def get_updated_shows(self, period = "day"):
        """Get a list of show ids which have been updated within this period."""
        fh = self.get_update_filehandle(period)
        if not fh:
            return []
        tree = ET.parse(fh)

        # FIXME: this finds various sub-records that result in (None) items in the array.
        series_nodes = tree.getiterator("Series")

        return [x.findtext("id") for x in series_nodes]

    def get_updated_episodes(self, period = "day"):
        """Get a list of episode ids which have been updated within this period."""
        fh = self.get_update_filehandle(period)
        if not fh:
            return []
        tree = ET.parse(fh)

        episode_nodes = tree.getiterator("Episode")

        return [(x.findtext("Series"), x.findtext("id")) for x in episode_nodes]

    def get_show_image_choices(self, show_id):
        """Get a list of image urls and types relating to this show."""
        url = "%s/series/%s/banners.xml" % (self.base_xml_url, show_id)
        data = urllib.urlopen(url)
        tree = ET.parse(data)

        images = []

        banner_data = tree.find("Banners")
        banner_nodes = tree.getiterator("Banner")
        for banner in banner_nodes:
            banner_path = banner.findtext("BannerPath")
            banner_type = banner.findtext("BannerType")
            if banner_type == 'season':
                banner_season = banner.findtext("Season")
            else:
                banner_season = ''
            banner_url = "%s/banners/%s" % (self.mirror_url, banner_path)

            images.append((banner_url, banner_type, banner_season))

        return images

    def get_updates(self, callback, period = "day"):
        """Return all series, episode, and banner updates w/o having to have it
        all in memory at once.  Also returns the Data timestamp and avoids the
        bogus "None" Series elements.  The callback routine should be defined as:
        my_callback(name, attrs) where name will be "Data", "Series", "Episode",
        or "Banner", and attrs will be a dict of the values (e.g. id, time, etc).
        """
        e = ExpatParseXml(callback)
        fh = self.get_update_filehandle(period)
        if fh:
            try:
                e.parse(fh)
            except expat.ExpatError:
                pass

class ExpatParseXml(object):
    def __init__(self, callback):
        self.el_name = None
        self.el_attr_name = None
        self.el_attrs = None
        self.el_callback = callback

        self.parser = expat.ParserCreate()
        self.parser.StartElementHandler = self.start_element
        self.parser.EndElementHandler = self.end_element
        self.parser.CharacterDataHandler = self.char_data

    def parse(self, fh):
        # Sadly ParseFile(fh) actually mangles the data, so we parse the file line by line:
        for line in fh:
            self.parser.Parse(line)

    def start_element(self, name, attrs):
        if not self.el_name:
            if name == 'Data':
                self.el_callback(name, attrs)
            else:
                self.el_name = name
                self.el_attrs = {}
        elif not self.el_attr_name:
            self.el_attr_name = name

    def end_element(self, name):
        if self.el_attr_name and name == self.el_attr_name:
            self.el_attr_name = None
        elif self.el_name and name == self.el_name:
            self.el_callback(self.el_name, self.el_attrs)
            self.el_name = None
            self.el_attr_name = None

    def char_data(self, data):
        if self.el_attr_name:
            if self.el_attrs.has_key(self.el_attr_name):
                self.el_attrs[self.el_attr_name] += data
            else:
                self.el_attrs[self.el_attr_name] = data

# vim: et
