from time import strptime, time, mktime, localtime
import os, sys, re, socket, urllib, unicodedata
from traceback import print_exc
from datetime import datetime, date, timedelta
from dateutil import tz
from operator import attrgetter, itemgetter
import xbmc, xbmcgui, xbmcaddon, xbmcvfs
from thetvdbapi import TheTVDB
from country_lookup import CountryLookup
if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson
# http://mail.python.org/pipermail/python-list/2009-June/540579.html
import _strptime

__addon__     = xbmcaddon.Addon()
__addonid__   = __addon__.getAddonInfo('id')
__addonname__ = __addon__.getAddonInfo('name')
__cwd__       = __addon__.getAddonInfo('path').decode('utf-8')
__author__    = __addon__.getAddonInfo('author')
__version__   = __addon__.getAddonInfo('version')
__language__  = __addon__.getLocalizedString
__useragent__ = "Mozilla/5.0 (Windows; U; Windows NT 5.1; fr; rv:1.9.0.1) Gecko/2008070208 Firefox/3.6"
__datapath__ = os.path.join( xbmc.translatePath( "special://profile/addon_data/" ).decode('utf-8'), __addonid__ )
__resource__  = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ).encode("utf-8") ).decode("utf-8")

sys.path.append(__resource__)

NEXTAIRED_DB = 'next.aired.db'
COUNTRY_DB = 'country.db'
USER_LOCK = 'user.lock'
BGND_LOCK = 'bgnd.lock'
BGND_STATUS = 'bgnd.status'
OLD_FILES = [ 'nextaired.db', 'next_aired.db', 'canceled.db', 'cancelled.db' ]

STATUS = { '0' : __language__(32201),
           '1' : __language__(32202),
           '2' : __language__(32203),
           '3' : __language__(32204),
           '4' : __language__(32205),
           '5' : __language__(32206),
           '6' : __language__(32207),
           '7' : __language__(32208),
           '8' : __language__(32209),
           '9' : __language__(32210),
           '10' : __language__(32211),
           '11' : __language__(32212),
           '-1' : ''}

STATUS_ID = { 'Returning Series' : '0',
              'Canceled/Ended' : '1',
              'TBD/On The Bubble' : '2',
              'In Development' : '3',
              'New Series' : '4',
              'Never Aired' : '5',
              'Final Season' : '6',
              'On Hiatus' : '7',
              'Pilot Ordered' : '8',
              'Pilot Rejected' : '9',
              'Canceled' : '10',
              'Ended' : '11',
              '' : '-1'}

# Get localized date format
DATE_FORMAT = xbmc.getRegion('dateshort').lower()
if DATE_FORMAT[0] == 'd':
    DATE_FORMAT = '%d-%m-%y'
elif DATE_FORMAT[0] == 'm':
    DATE_FORMAT = '%m-%d-%y'

MAIN_DB_VER = 1
COUNTRY_DB_VER = 1

if not xbmcvfs.exists(__datapath__):
    xbmcvfs.mkdir(__datapath__)

# TODO make this settable via the command-line?
verbosity = 2 # XXX change to 1 after initial testing?

# if level <= 0, sends LOGERROR msg.  For positive values, sends LOGNOTICE
# if level <= verbosity, else LOGDEBUG.  If level is omitted, we assume 10.
def log(txt, level=10):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (__addonid__, txt)
    log_level = (xbmc.LOGERROR if level <= 0 else (xbmc.LOGNOTICE if level <= verbosity else xbmc.LOGDEBUG))
    xbmc.log(msg=message.encode("utf-8"), level=log_level)

def footprints():
    log("### %s starting ..." % __addonname__, level=2)
    log("### author: %s" % __author__, level=3)
    log("### version: %s" % __version__, level=2)
    log("### dateformat: %s" % DATE_FORMAT, level=3)

def _unicode( text, encoding='utf-8' ):
    try: text = unicode( text, encoding )
    except: pass
    return text

def normalize_string( text ):
    try: text = unicodedata.normalize( 'NFKD', _unicode( text ) ).encode( 'ascii', 'ignore' )
    except: pass
    return text

class NextAired:
    def __init__(self):
        footprints()
        self.WINDOW = xbmcgui.Window( 10000 )
        self.set_today()
        self.days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        self.ampm = xbmc.getCondVisibility('substring(System.Time,Am)') or xbmc.getCondVisibility('substring(System.Time,Pm)')
        self._parse_argv()
        if self.TVSHOWTITLE:
            self.return_properties(self.TVSHOWTITLE)
        elif self.BACKEND:
            self.run_backend()
        elif self.SILENT == "":
            self.show_gui()
        else:
            for old_file in OLD_FILES:
                self.rm_file(old_file)
            self.do_background_updating()

    def _parse_argv( self ):
        try:
            params = dict( arg.split( "=" ) for arg in sys.argv[ 1 ].split( "&" ) )
        except:
            params = {}
        log("### params: %s" % params, level=5)
        self.SILENT = params.get( "silent", "" )
        self.BACKEND = params.get( "backend", False )
        self.TVSHOWTITLE = params.get( "tvshowtitle", False )
        self.FORCEUPDATE = __addon__.getSetting("ForceUpdate") == "true"
        self.RESET = params.get( "reset", False )

    def set_today(self):
        self.now = time()
        self.date = date.today()
        self.datestr = str(self.date)
        self.in_dst = localtime().tm_isdst
        self.day_limit = str(self.date + timedelta(days=6))
        self.this_year_regex = re.compile(r', %s$' % self.date.strftime('%Y'))

    def do_background_updating(self):
        update_every = 1
        while not xbmc.abortRequested:
            log("### performing background update", level=2)
            self.update_data(update_every)
            log("### background update finished", level=2)
            self.nextlist = [] # Discard the in-memory data until the next update
            while not xbmc.abortRequested:
                try:
                    update_every = int(__addon__.getSetting('update_every')) # in hours
                    update_every *= 60*60 # into seconds
                except:
                    update_every = 0
                if update_every and time() - self.last_update >= update_every:
                    break
                xbmc.sleep(1000)
        self.close("xbmc is closing, stop script")

    def load_data(self):
        if self.RESET:
            self.rm_file(NEXTAIRED_DB)
            self.rm_file(COUNTRY_DB)

        self.set_today()

        # Snag our TV-network -> Country + timezone mapping DB, or create it.
        cl = self.get_list(COUNTRY_DB)
        if cl and len(cl) == 3 and self.now - cl[2] < 7*24*60*60: # We'll recreate it every week.
            self.country_dict = cl[0]
        else:
            try:
                log("### grabbing a new country mapping list", level=1)
                self.country_dict = CountryLookup().get_country_dict()
                self.save_file([self.country_dict, COUNTRY_DB_VER, self.now], COUNTRY_DB)
            except:
                # Well, if we couldn't grab a new one, lets try to keep using the old...
                self.country_dict = (cl[0] if cl and len(cl) == 3 else {})

        ep_list = self.get_list(NEXTAIRED_DB)
        show_dict = (ep_list.pop(0) if ep_list else {})
        self.last_update = (ep_list.pop() if ep_list else None)
        db_ver = (ep_list.pop() if ep_list else 0)
        if not self.last_update:
            if self.RESET:
                log("### starting without prior data (DB RESET requested)", level=1)
            elif ep_list:
                log("### ignoring bogus %s file" % NEXTAIRED_DB, level=1)
            else:
                log("### no prior data found", level=1)
            show_dict = {}
            self.last_update = 0
        elif db_ver != MAIN_DB_VER:
            self.upgrade_data_format(show_dict, db_ver)

        self.RESET = False # Make sure we don't honor this multiple times.

        elapsed_secs = self.now - self.last_update
        return (show_dict, elapsed_secs)

    def update_data(self, update_after_seconds):
        self.nextlist = []
        show_dict, elapsed_secs = self.load_data()
        if update_after_seconds == 0:
            update_after_seconds = 100*365*24*60*60

        # This should prevent the background and user code from updating the DB at the same time.
        if self.SILENT != "":
            if elapsed_secs < update_after_seconds:
                return
            # Background updating: we will just skip our update if the user is doing an update.
            self.max_fetch_failures = 8
            self.save_file([self.now], BGND_LOCK)
            locked_for_update = True
            xbmc.sleep(2000) # try to avoid a race-condition
            user_lock = self.get_list(USER_LOCK)
            if user_lock:
                if self.now - user_lock[0] <= 10*60:
                    self.rm_file(BGND_LOCK)
                    self.last_update = self.now
                    return
                # User's lock has sat around for too long, so just remove it.
                self.rm_file(USER_LOCK)
            socket.setdefaulttimeout(60)
        elif elapsed_secs >= update_after_seconds: # We only lock if we're going to do some updating.
            # User updating: we will wait for a background update to finish, then see if we have recent data.
            DIALOG_PROGRESS = xbmcgui.DialogProgress()
            DIALOG_PROGRESS.create(__language__(32101), __language__(32102))
            self.max_fetch_failures = 4
            # Create our user-lock file and check if the background updater is running.
            self.save_file([self.now], USER_LOCK)
            locked_for_update = True
            newest_time = 0
            while 1:
                bg_lock = self.get_list(BGND_LOCK)
                if not bg_lock:
                    break
                if newest_time == 0:
                    newest_time = bg_lock[0]
                bg_status = self.get_list(BGND_STATUS)
                if bg_status:
                    DIALOG_PROGRESS.update(bg_status[1], __language__(32102), bg_status[2])
                    if DIALOG_PROGRESS.iscanceled():
                        DIALOG_PROGRESS.close()
                        xbmcgui.Dialog().ok(__language__(32103),__language__(32104))
                        self.rm_file(USER_LOCK)
                        locked_for_update = False
                        break
                    if bg_status[0] > newest_time:
                        newest_time = bg_status[0]
                if time() - newest_time > 2*60:
                    # Background lock has sat around for too long, so just remove it.
                    self.rm_file(BGND_LOCK)
                    newest_time = 0
                    break
                xbmc.sleep(500)
            if newest_time:
                # If we had to wait for the bgnd updater, re-read the data and unlock if they did an update.
                show_dict, elapsed_secs = self.load_data()
                if locked_for_update and elapsed_secs < update_after_seconds:
                    self.rm_file(USER_LOCK)
                    locked_for_update = False
            socket.setdefaulttimeout(10)
        else:
            locked_for_update = False

        title_dict = {}
        for tid in show_dict:
            show = show_dict[tid]
            show['unused'] = True
            title_dict[show['localname']] = tid

        tvdb = TheTVDB()
        tv_up = tvdb_updater()

        if locked_for_update:
            # This typically asks TheTVDB for an update-zip file and tweaks the show_dict to note needed updates.
            need_full_scan = tv_up.note_updates(tvdb, show_dict, elapsed_secs)
            self.last_update = self.now
        else:
            need_full_scan = False
            # A max-fetch of 0 disables all updating.
            self.max_fetch_failures = 0

        TVlist = self.listing()
        total_show = len(TVlist)
        if total_show == 0:
            self.close("error listing")

        count = 0
        id_re = re.compile(r"http%3a%2f%2fthetvdb\.com%2f[^']+%2f([0-9]+)-")
        num_re = re.compile(r"^([0-9]+)$")
        for show in TVlist:
            count += 1
            percent = int(float(count * 100) / total_show)
            if self.SILENT != "":
                self.save_file([time(), percent, show[0]], BGND_STATUS)
            elif locked_for_update and self.max_fetch_failures > 0:
                DIALOG_PROGRESS.update( percent , __language__(32102) , "%s" % show[0] )
                if DIALOG_PROGRESS.iscanceled():
                    DIALOG_PROGRESS.close()
                    xbmcgui.Dialog().ok(__language__(32103),__language__(32104))
                    self.max_fetch_failures = 0
            log( "### %s" % show[0] )
            current_show = {
                    "localname": show[0],
                    "path": show[1],
                    "art": show[2],
                    "dbid": show[3],
                    "thumbnail": show[4],
                    }
            # Try to figure out what the tvdb number is by using the art URLs and the imdbnumber value
            m2 = id_re.search(str(show[2]))
            m2_num = int(m2.group(1)) if m2 else 0
            m4 = id_re.search(show[4])
            m4_num = int(m4.group(1)) if m4 else 0
            m5 = num_re.match(show[5])
            m5_num = int(m5.group(1)) if m5 else 0
            if m5_num and (m2_num == m5_num or m4_num == m5_num):
                # Most shows will be in agreement on the id when the scraper is using thetvdb.
                tid = m5_num
            else:
                old_id = title_dict.get(current_show["localname"], 0)
                if old_id and (m2_num == old_id or m4_num == old_id):
                    tid = old_id
                elif m2_num and m2_num == m4_num:
                    # This will override the old_id value if both artwork URLs change.
                    tid = m2_num
                elif old_id:
                    tid = old_id
                else:
                    tid = 0 # We'll query it from thetvdb.com

            try:
                prior_data = show_dict[tid]
                if not prior_data.has_key('unused'):
                    continue # How'd we get a duplicate?? Skip it...
                del prior_data['unused']
                while len(prior_data['episodes']) > 1 and prior_data['episodes'][1]['aired'][:10] < self.datestr:
                    prior_data['episodes'].pop(0)
            except:
                prior_data = None

            if self.max_fetch_failures > 0:
                tid = self.check_show_info(tvdb, tid, current_show, prior_data)
            else:
                tid = -tid
            if tid <= 0:
                if not prior_data or tid == 0:
                    continue
                for item in prior_data:
                    if not current_show.has_key(item):
                        current_show[item] = prior_data[item]
                tid = -tid
            if current_show.get('canceled', False):
                log("### Canceled/Ended", level=4)
            log( "### %s" % current_show )
            show_dict[tid] = current_show

        # If we did a lot of work, make sure we save it prior to doing anything else.
        # This ensures that a bug in the following code won't make us redo everything.
        if need_full_scan and locked_for_update:
            self.save_file([show_dict, MAIN_DB_VER, self.last_update], NEXTAIRED_DB)

        if show_dict:
            log("### data available", level=5)
            remove_list = []
            for tid in show_dict:
                show = show_dict[tid]
                if show.has_key('unused'):
                    remove_list.append(tid)
                    continue
                if len(show['episodes']) > 1:
                    show['RFC3339'] = show['episodes'][1]['aired']
                    self.nextlist.append(show)
                elif show.has_key('RFC3339'):
                    del show['RFC3339']
            for tid in remove_list:
                log('### Removing obsolete show %s' % show_dict[tid]['localname'], level=2)
                del show_dict[tid]
            self.nextlist.sort(key=itemgetter('RFC3339'))
            log("### next list: %s shows ### %s" % (len(self.nextlist) , self.nextlist), level=3)
            self.check_today_show()
            self.push_data()
        else:
            log("### no current show data...", level=5)

        if locked_for_update:
            self.save_file([show_dict, MAIN_DB_VER, self.last_update], NEXTAIRED_DB)

        if self.SILENT != "":
            self.rm_file(BGND_LOCK)
            xbmc.sleep(1000)
            self.save_file([time(), 0, '...'], BGND_STATUS)
        elif locked_for_update:
            DIALOG_PROGRESS.close()
            self.rm_file(USER_LOCK)

    def listing(self):
        json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"properties": ["title", "file", "thumbnail", "art", "imdbnumber"], "sort": { "method": "title" } }, "id": 1}')
        json_query = unicode(json_query, 'utf-8', errors='ignore')
        json_response = simplejson.loads(json_query)
        log("### %s" % json_response)
        TVlist = []
        if json_response['result'].has_key('tvshows'):
            for item in json_response['result']['tvshows']:
                tvshowname = normalize_string(item['title'])
                path = item['file']
                art = item['art']
                thumbnail = item['thumbnail']
                dbid = 'videodb://2/2/' + str(item['tvshowid']) + '/'
                TVlist.append((tvshowname, path, art, dbid, thumbnail, item['imdbnumber']))
        log( "### list: %s" % TVlist )
        return TVlist

    def check_show_info(self, tvdb, tid, current_show, prior_data):
        name = current_show['localname']
        log("### check if %s is up-to-date" % name, level=3)
        if tid == 0:
            log("### searching for thetvdb ID by show name", level=3)
            show_list = tvdb.get_matching_shows(name)
            if not show_list:
                log("### no match found", level=3)
                return 0
            got_id, got_title, got_tt_id = show_list[0]
            tid = int(got_id)
            log("### found id of %d" % tid, level=3)
        else:
            log("### thetvdb id = %d" % tid, level=5)
        # If the prior_data isn't in need of an update, use it unchanged.
        if prior_data:
            earliest_id, eps_last_updated = prior_data.get('eps_changed', (None, 0))
            if earliest_id is None:
                eps_last_updated = prior_data['eps_last_updated']
            show_changed = prior_data.get('show_changed', 0)
            if earliest_id is None and prior_data.has_key('TZ'):
                earliest_id = 1 # XXX temporary heuristic to force updating of timezone info
            if show_changed:
                if earliest_id is None:
                    earliest_id = 0
            elif earliest_id is None:
                log("### no changes needed", level=5)
                return -tid
            for ep in prior_data['episodes']:
                if ep['id'] and ep['id'] < earliest_id:
                    earliest_id = ep['id']
        else:
            show_changed = 0
            earliest_id = 1
            eps_last_updated = 0

        if earliest_id != 0:
            log("### earliest_id = %d" % earliest_id, level=5)
            for cnt in range(2):
                log("### getting series & episode information for %s" % name, level=2)
                try:
                    result = tvdb.get_show_and_episodes(tid, earliest_id)
                    break
                except Exception, e:
                    log('### ERROR returned by get_show_and_episodes(): %s' % e, level=0)
                    self.max_fetch_failures -= 1
                    result = None
            if result:
                show = result[0]
                episodes = result[1]
            else:
                show = None
        else: # earliest_id == 0 when only the series-info changed
            for cnt in range(2):
                log("### getting series information for %s" % name, level=2)
                try:
                    show = tvdb.get_show(tid)
                    break
                except Exception, e:
                    log('### ERROR returned by get_show(): %s' % e, level=0)
                    self.max_fetch_failures -= 1
                    show = None
            episodes = None
        if not show:
            if prior_data:
                log("### no result: continuing to use the old data", level=1)
            else:
                log("### no result and no prior data", level=1)
            return -tid

        country = (self.country_dict.get(show.network, 'Unknown') if show.network else 'Unknown')
        # XXX TODO allow the user to specify an override country that gets the local timezone.
        tzone = CountryLookup.get_country_timezone(country, self.in_dst)
        if not tzone:
            tzone = ''
        tz_re = re.compile(r"([-+])(\d\d):(\d\d)")
        m = tz_re.match(tzone)
        if m:
            tz_offset = (int(m.group(2)) * 3600) + (int(m.group(3)) * 60)
            if m.group(1) == '-':
                tz_offset *= -1
        else:
            tz_offset = 1 * 3600 # Default to +01:00
        try:
            airtime = TheTVDB.convert_time(show.airs_time)
        except:
            airtime = None
        local_airtime = airtime if airtime else TheTVDB.convert_time('00:00')
        local_airtime = datetime.combine(self.date, local_airtime).replace(tzinfo=tz.tzoffset(None, tz_offset))
        if airtime: # Don't backtrack an assumed midnight time (for an invalid airtime) into the prior day.
            local_airtime = local_airtime.astimezone(tz.tzlocal())
        airtime_fmt = '%I:%M %p' if self.ampm else '%H:%M'

        current_show['Show Name'] = show.name
        if show.first_aired:
            current_show['Premiered'] = show.first_aired.strftime('%Y')
            current_show['Started'] = show.first_aired.strftime('%b/%d/%Y')
        else:
            current_show['Premiered'] = current_show['Started'] = ""
        current_show['Country'] = country
        current_show['Status'] = show.status
        current_show['Genres'] = show.genre.strip('|').replace('|', ' | ')
        current_show['Network'] = show.network
        current_show['Airtime'] = local_airtime.strftime(airtime_fmt) if airtime else '??:??'
        current_show['Runtime'] = show.runtime

        can_re = re.compile(r"canceled|ended", re.IGNORECASE)
        if can_re.search(show.status):
            current_show['canceled'] = True
        elif current_show.has_key('canceled'):
            del current_show['canceled']

        if episodes is not None:
            episode_list = []

            max_eps_utime = 0
            if episodes:
                good_eps = []
                for ep in episodes:
                    ep.id = int(ep.id)
                    ep.season_number = int(ep.season_number)
                    ep.episode_number = int(ep.episode_number)
                    if ep.last_updated_utime > max_eps_utime:
                        max_eps_utime = ep.last_updated_utime
                    log("### fetched ep=%d last_updated=%d first_aired=%s" % (ep.id, ep.last_updated_utime, ep.first_aired))
                    aired = TheTVDB.convert_date(ep.first_aired)
                    if not aired:
                        continue
                    ep.first_aired = local_airtime + timedelta(days = (aired - self.date).days)
                    good_eps.append(ep)
                episodes = sorted(good_eps, key=attrgetter('first_aired', 'season_number', 'episode_number'))
            if episodes and episodes[0].first_aired.date() < self.date:
                while len(episodes) > 1 and episodes[1].first_aired.date() < self.date:
                    ep = episodes.pop(0)
            else: # If we have no prior episodes, prepend a "None" episode
                episode_list.append({ 'id': None })

            for ep in episodes:
                cur_ep = {
                        'id': ep.id,
                        'name': ep.name,
                        'number': '%02dx%02d' % (ep.season_number, ep.episode_number),
                        'aired': ep.first_aired.isoformat(),
                        'wday': self.days[ep.first_aired.weekday()]
                        }
                episode_list.append(cur_ep)

            current_show['episodes'] = episode_list
        elif prior_data:
            max_eps_utime = eps_last_updated
            current_show['episodes'] = prior_data['episodes']
            if current_show['Airtime'] != prior_data['Airtime']:
                for ep in current_show['episodes']:
                    if not ep['id']:
                        continue
                    aired = TheTVDB.convert_date(ep['aired'][:10])
                    aired = local_airtime + timedelta(days = (aired - self.date).days)
                    ep['aired'] = aired.isoformat()
                    ep['wday'] = self.days[aired.weekday()]
        else:
            max_eps_utime = 0
            current_show['episodes'] = [{ 'id': None }]

        if prior_data:
            if prior_data.has_key('show_changed') and show.last_updated_utime < show_changed:
                log("### didn't get latest show info yet (%d < %d)" % (show.last_updated_utime, show_changed), level=2)
                current_show['show_changed'] = show_changed
            if prior_data.has_key('eps_changed') and max_eps_utime < eps_last_updated:
                log("### didn't get latest episode info yet (%d < %d)" % (max_eps_utime, eps_last_updated), level=2)
                current_show['eps_changed'] = (earliest_id, eps_last_updated)

        current_show['last_updated'] = max(show_changed, show.last_updated_utime)
        current_show['eps_last_updated'] = max(eps_last_updated, max_eps_utime)
        return tid

    @staticmethod
    def upgrade_data_format(show_dict, from_ver):
        log("### upgrading DB from version %d to %d" % (from_ver, MAIN_DB_VER), level=1)
        # We'll add code here if the db changes

    def set_episode_info(self, label, prefix, when, ep):
        if ep and ep['id']:
            name = ep['name']
            number = ep['number']
            aired = self.this_year_regex.sub('', TheTVDB.convert_date(ep['aired'][:10]).strftime('%a, %b %d, %Y'))
        else:
            name = number = aired = ''
        num_array = number.split('x')
        num_array.extend([''])

        label.setProperty(prefix + when + 'Date', aired)
        label.setProperty(prefix + when + 'Title', name)
        label.setProperty(prefix + when + 'Number', number)
        label.setProperty(prefix + when + 'SeasonNumber', num_array[0])
        label.setProperty(prefix + when + 'EpisodeNumber', num_array[1])

    def check_today_show(self):
        self.set_today()
        self.todayshow = 0
        self.todaylist = []
        log( "### %s" % self.datestr )
        for show in self.nextlist:
            name = show["localname"]
            when = show["RFC3339"]
            log( "################" )
            log( "### %s" % name )
            if when[:10] == self.datestr:
                self.todayshow += 1
                self.todaylist.append(name)
                log( "### TODAY" )
            log( "### %s" % when )
        log( "### today show: %s - %s" % ( self.todayshow , str(self.todaylist).strip("[]") ) )

    @staticmethod
    def get_list(listname):
        path = os.path.join( __datapath__ , listname )
        if xbmcvfs.exists(path):
            log( "### Load list: %s" % path )
            return NextAired.load_file(path)
        else:
            log( "### Load list: %s not found!" % path )
            return []

    @staticmethod
    def load_file(file_path):
        try:
            return eval( file( file_path, "r" ).read() )
        except:
            print_exc()
            log("### ERROR could not load file %s" % file_path, level=0)
            return []

    @staticmethod
    def save_file(txt, filename):
        path = os.path.join( __datapath__ , filename )
        try:
            if txt:
                file( path , "w" ).write( repr( txt ) )
            else:
                self.rm_file(filename)
        except:
            print_exc()
            log("### ERROR could not save file %s" % path, level=0)

    @staticmethod
    def rm_file(filename):
        path = os.path.join(__datapath__, filename)
        try:
            if xbmcvfs.exists(path):
                xbmcvfs.delete(path)
        except:
            pass

    def push_data(self):
        try:
            oldTotal = int(self.WINDOW.getProperty("NextAired.Total"))
        except:
            oldTotal = 1
        self.WINDOW.setProperty("NextAired.Total" , str(len(self.nextlist)))
        self.WINDOW.setProperty("NextAired.TodayTotal" , str(self.todayshow))
        self.WINDOW.setProperty("NextAired.TodayShow" , str(self.todaylist).strip("[]"))
        for count in range(oldTotal):
            self.WINDOW.clearProperty("NextAired.%d.Label" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Thumb" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.AirTime" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Path" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Library" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Status" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.StatusID" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Network" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Started" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Classification" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Genre" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Premiered" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Country" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Runtime" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Fanart" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Art(fanart)" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Art(poster)" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Art(landscape)" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Art(banner)" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Art(clearlogo)" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Art(characterart)" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Art(clearart)" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Today" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.NextDate" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.NextTitle" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.NextNumber" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.NextEpisodeNumber" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.NextSeasonNumber" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.LatestDate" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.LatestTitle" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.LatestNumber" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.LatestEpisodeNumber" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.LatestSeasonNumber" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.Airday" % ( count + 1, ))
            self.WINDOW.clearProperty("NextAired.%d.ShortTime" % ( count + 1, ))
        self.count = 0
        for current_show in self.nextlist:
            if ((current_show.get("RFC3339" , "" )[:10] == self.datestr) or (__addon__.getSetting( "ShowAllTVShowsOnHome" ) == 'true')):
                self.count += 1
                self.set_labels('windowpropertytoday', current_show)

    def show_gui(self):
        if self.FORCEUPDATE:
            update_after = 1
        else:
            try:
                update_after = int(__addon__.getSetting('update_after'))*60 # mins -> seconds
            except:
                update_after = 0
        self.update_data(update_after)
        weekday = self.date.weekday()
        self.WINDOW.setProperty("NextAired.TodayDate", self.date.strftime(DATE_FORMAT))
        for count in range(0, 7):
            date = self.date
            if count != weekday:
                date += timedelta(days = (count - weekday + 7) % 7)
            self.WINDOW.setProperty("NextAired.%d.Date" % (count + 1), date.strftime(DATE_FORMAT))
        import next_aired_dialog
        next_aired_dialog.MyDialog(self.nextlist, self.set_labels)

    def run_backend(self):
        self._stop = False
        self.previousitem = ''
        ep_list = self.get_list(NEXTAIRED_DB)
        show_dict = (ep_list.pop(0) if ep_list else {})
        if not show_dict:
            self._stop = True
        while not self._stop:
            self.selecteditem = xbmc.getInfoLabel("ListItem.TVShowTitle")
            if self.selecteditem != self.previousitem:
                self.WINDOW.clearProperty("NextAired.Label")
                self.previousitem = self.selecteditem
                for tid in show_dict:
                    item = show_dict[tid]
                    if self.selecteditem == item["localname"]:
                        self.set_labels('windowproperty', item)
                        break
            xbmc.sleep(100)
            if not xbmc.getCondVisibility("Window.IsVisible(10025)"):
                self.WINDOW.clearProperty("NextAired.Label")
                self._stop = True

    def return_properties(self,tvshowtitle):
        ep_list = self.get_list(NEXTAIRED_DB)
        show_dict = (ep_list.pop(0) if ep_list else {})
        log("### return_properties started", level=6)
        if show_dict:
            self.WINDOW.clearProperty("NextAired.Label")
            for tid in show_dict:
                item = show_dict[tid]
                if tvshowtitle == item["localname"]:
                    self.set_labels('windowproperty', item)

    def set_labels(self, infolabel, item, want_episode = None):
        art = item.get("art", "")
        if (infolabel == 'windowproperty') or (infolabel == 'windowpropertytoday'):
            label = xbmcgui.Window( 10000 )
            if infolabel == "windowproperty":
                prefix = 'NextAired.'
            else:
                prefix = 'NextAired.' + str(self.count) + '.'
                if __addon__.getSetting( "ShowAllTVShowsOnHome" ) == 'true':
                    label.setProperty('NextAired.' + "ShowAllTVShows", "true")
                else:
                    label.setProperty('NextAired.' + "ShowAllTVShows", "false")
            label.setProperty(prefix + "Label", item.get("localname", ""))
            label.setProperty(prefix + "Thumb", item.get("thumbnail", ""))
        else:
            label = xbmcgui.ListItem()
            prefix = ''
            label.setLabel(item.get("localname", ""))
            label.setThumbnailImage(item.get("thumbnail", ""))

        if want_episode:
            next_ep = want_episode
            latest_ep = None
            airdays = next_ep['wday']
        else:
            ep_len = len(item['episodes'])
            next_ep = item['episodes'][1] if ep_len > 1 else None
            latest_ep = item['episodes'][0]
            airdays = []
            if ep_len > 1:
                for ep in item['episodes'][1:]:
                    if ep['aired'][:10] > self.day_limit:
                        break
                    airdays.append(ep['wday'])
            airdays = ', '.join(airdays)
        is_today = 'True' if next_ep and next_ep['aired'][:10] == self.datestr else 'False'

        status = item.get("Status", "")
        try:
            status_id = STATUS_ID[status]
            status = STATUS[status_id]
        except:
            status_id = '-1'

        label.setProperty(prefix + "AirTime", '%s at %s' % (airdays, item.get("Airtime", "")))
        label.setProperty(prefix + "Path", item.get("path", ""))
        label.setProperty(prefix + "Library", item.get("dbid", ""))
        label.setProperty(prefix + "Status", status)
        label.setProperty(prefix + "StatusID", status_id)
        label.setProperty(prefix + "Network", item.get("Network", ""))
        label.setProperty(prefix + "Started", item.get("Started", ""))
        # XXX Note that Classification is always unset at the moment!
        label.setProperty(prefix + "Classification", item.get("Classification", ""))
        label.setProperty(prefix + "Genre", item.get("Genres", ""))
        label.setProperty(prefix + "Premiered", item.get("Premiered", ""))
        label.setProperty(prefix + "Country", item.get("Country", ""))
        label.setProperty(prefix + "Runtime", item.get("Runtime", ""))
        # Keep old fanart property for backwards compatibility
        label.setProperty(prefix + "Fanart", art.get("fanart", ""))
        # New art properties
        label.setProperty(prefix + "Art(fanart)", art.get("fanart", ""))
        label.setProperty(prefix + "Art(poster)", art.get("poster", ""))
        label.setProperty(prefix + "Art(banner)", art.get("banner", ""))
        label.setProperty(prefix + "Art(landscape)", art.get("landscape", ""))
        label.setProperty(prefix + "Art(clearlogo)", art.get("clearlogo", ""))
        label.setProperty(prefix + "Art(characterart)", art.get("characterart", ""))
        label.setProperty(prefix + "Art(clearart)", art.get("clearart", ""))
        label.setProperty(prefix + "Today", is_today)
        label.setProperty(prefix + "AirDay", airdays)
        label.setProperty(prefix + "ShortTime", item.get("Airtime", ""))

        # This sets NextDate, NextTitle, etc.
        self.set_episode_info(label, prefix, 'Next', next_ep)
        # This sets LatestDate, LatestTitle, etc.
        self.set_episode_info(label, prefix, 'Latest', latest_ep)

        if want_episode:
            return label

    def close(self , msg ):
        log( "### %s" % msg )
        exit

class tvdb_updater:
    def __init__(self):
        pass # Nothing to do for now...

    def note_updates(self, tvdb, show_dict, elapsed_secs):
        self.show_dict = show_dict

        if elapsed_secs < 24*60*60:
            period = 'day'
        elif elapsed_secs < 7*24*60*60:
            period = 'week'
        elif elapsed_secs < 30*24*60*60:
            period = 'month'
        else:
            # Flag all non-canceled shows as needing new data
            for tid in self.show_dict:
                show = self.show_dict[tid]
                if not show.get('canceled', False):
                    show['show_changed'] = 1
                    show['eps_changed'] = (1, 0)
            return True # Alert caller that a full-scan was done.

        log("### Update period: %s (%d mins)" % (period, int(elapsed_secs / 60)), level=2)

        try:
            tvdb.get_updates(self.change_callback, period)
        except Exception, e:
            log('### ERROR retreiving updates from thetvdb.com: %s' % e, level=0)
            self.max_fetch_failures -= 1

        return False

    def change_callback(self, name, attrs):
        if name == 'Episode':
            episode_id = int(attrs['id'])
            series_id = int(attrs['Series'])
        elif name == 'Series':
            series_id = int(attrs['id'])
            episode_id = 0
        elif name == 'Data':
            when = int(attrs['time'])
            # Do something with this?
            return
        else:
            return # Ignore Banner and anything else that may show up
        try:
            show = self.show_dict[series_id]
        except:
            return # Ignore shows we don't care about
        when = int(attrs['time'])
        if episode_id == 0:
            if when <= show['last_updated']:
                return
            log("### Found series change (series: %d, time: %d) for %s" % (series_id, when, show['localname']), level=2)
            show['show_changed'] = when
        else:
            if when <= show['eps_last_updated']:
                return
            log("### Found episode change (series: %d, ep: %d, time=%d) for %s" % (series_id, episode_id, when, show['localname']), level=2)
            earliest_id, latest_time = show.get('eps_changed', (episode_id, when))
            if episode_id < earliest_id:
                earliest_id = episode_id
            if when > latest_time:
                latest_time = when
            show['eps_changed'] = (earliest_id, latest_time)
        return

if ( __name__ == "__main__" ):
    NextAired()

# vim: et
