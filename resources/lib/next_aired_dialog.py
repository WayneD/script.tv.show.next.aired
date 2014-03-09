from traceback import print_exc
from time import mktime
from datetime import date, timedelta
import xbmc, xbmcgui, xbmcaddon, time

__addon__   = xbmcaddon.Addon()
__addonid__ = __addon__.getAddonInfo('id')
__cwd__     = __addon__.getAddonInfo('path').decode("utf-8")

def log(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (__addonid__, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGDEBUG)

class Gui( xbmcgui.WindowXML ):
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXML.__init__( self )
        self.nextlist = kwargs['listing']
        self.setLabels = kwargs['setLabels']
        self.niceDate = kwargs['niceDate']
        self.scanDays = kwargs['scanDays']
        self.todayStyle = kwargs['todayStyle']
        self.wantYesterday = kwargs['wantYesterday']
        # We allow today + 2 weeks worth of "upcoming" days.
        if self.scanDays > 15:
            self.scanDays = 15
        if self.todayStyle:
            if self.wantYesterday:
                self.scanDays += 1
            self.cntr_cnt = self.scanDays
        else:
            self.cntr_cnt = 7
            self.wantYesterday = False

    def onInit(self):
        num = int( __addon__.getSetting( "ThumbType" ) )
        xbmc.executebuiltin( "SetProperty(TVGuide.ThumbType,%i,Home)" % num )
        if __addon__.getSetting( "PreviewThumbs" ) == 'true':
            xbmc.executebuiltin( "SetProperty(TVGuide.PreviewThumbs,1,Home)" )
        else:
            xbmc.executebuiltin( "ClearProperty(TVGuide.PreviewThumbs,Home)" )
        if __addon__.getSetting( "BackgroundFanart" ) == 'true':
            xbmc.executebuiltin( "SetProperty(TVGuide.BackgroundFanart,1,Home)" )
        else:
            xbmc.executebuiltin( "ClearProperty(TVGuide.BackgroundFanart,Home)" )
        self.settingsOpen = False
        self.start_day = date.today()
        if not self.todayStyle:
            self.first_num = 200
            shift_cnt = self.start_day.weekday()
        elif self.wantYesterday:
            self.first_num = 200
            shift_cnt = 1
            self.start_day -= timedelta(days=1) # start with yesterday
        else:
            self.first_num = 201
            shift_cnt = 0

        self.cntr_nums = range(self.first_num, self.first_num + self.cntr_cnt)
        for j in range(0, shift_cnt):
            self.cntr_nums.append(self.cntr_nums.pop(0))
        self.set_properties()
        self.fill_containers()
        self.set_focus()

    def set_properties(self):
        self.listitems = []
        for c in self.cntr_nums:
            self.listitems.append([])
            cntr_day = self.start_day + timedelta(days = c - self.first_num)
            if self.todayStyle and c in (200, 201):
                if c == 200:
                    wday = __addon__.getLocalizedString(32018) # Yesterday
                else:
                    wday = xbmc.getLocalizedString(33006) # Today
            else:
                wday = xbmc.getLocalizedString(cntr_day.weekday() + 11)
            xbmc.executebuiltin('SetProperty(NextAired.%d.Wday,%s,Home)' % (c, wday))
            xbmc.executebuiltin('SetProperty(NextAired.%d.Date,"%s",Home)' % (c, self.niceDate(cntr_day, omit_year=0)))
        for c in range(200, 216):
            if c not in self.cntr_nums:
                xbmc.executebuiltin('clearProperty(NextAired.%d.Wday,Home)' % c)
                xbmc.executebuiltin('clearProperty(NextAired.%d.Date,Home)' % c)
        min_day = str(self.start_day)
        max_day = str(self.start_day + timedelta(days = self.scanDays-1))
        episodes = []
        for show in self.nextlist:
            for ep_ndx in range(len(show['episodes'])):
                aired = show['episodes'][ep_ndx]['aired']
                if aired[:10] < min_day:
                    continue
                if aired[:10] > max_day:
                    break
                episodes.append((aired, show, ep_ndx))

        episodes.sort(key=lambda x: x[0])

        for aired, show, ep_ndx in episodes:
                listitem = self.setLabels('listitem', show, ep_ndx)
                if self.todayStyle:
                    ndx = (date(*map(int, aired[:10].split("-"))) - self.start_day).days
                else:
                    ndx = show['episodes'][ep_ndx]['wday']
                self.listitems[ndx].append(listitem)

    def fill_containers(self):
        for c in self.cntr_nums:
            self.getControl(c).reset()
            self.getControl(c).addItems(self.listitems[c - self.first_num])

    def set_focus(self):
        focus_to = 8
        for c in self.cntr_nums:
            if self.listitems[c - self.first_num]:
                focus_to = c
                break
        self.setFocus(self.getControl(focus_to))

    def onClick(self, controlID):
        if controlID == 8:
            self.settingsOpen = True
            __addon__.openSettings()
            self.close()
        elif controlID in self.cntr_nums:
            listitem = self.getControl( controlID ).getSelectedItem()
            library = listitem.getProperty('Library')
            xbmc.executebuiltin('ActivateWindow(Videos,' + library + ',return)')

    def onFocus(self, controlID):
        pass

    def onAction( self, action ):
        if self.settingsOpen and action.getId() in ( 7, 10, 92, ):
            num = int( __addon__.getSetting( "ThumbType" ) )
            xbmc.executebuiltin( "SetProperty(TVGuide.ThumbType,%i,Home)" % num )
            if __addon__.getSetting( "PreviewThumbs" ) == 'true':
                xbmc.executebuiltin( "SetProperty(TVGuide.PreviewThumbs,1,Home)" )
            else:
                xbmc.executebuiltin( "ClearProperty(TVGuide.PreviewThumbs,Home)" )
            if __addon__.getSetting( "BackgroundFanart" ) == 'true':
                xbmc.executebuiltin( "SetProperty(TVGuide.BackgroundFanart,1,Home)" )
            else:
                xbmc.executebuiltin( "ClearProperty(TVGuide.BackgroundFanart,Home)" )
            self.settingsOpen = False
        if action.getId() in ( 9, 10, 92, 216, 247, 257, 275, 61467, 61448, ):
            self.close()

def MyDialog(tv_list, setLabels, niceDate, scanDays, todayStyle, wantYesterday):
    xml = "script-NextAired-TVGuide%s.xml" % (2 if todayStyle else "")
    w = Gui(xml, __cwd__, "Default", listing=tv_list, setLabels=setLabels, niceDate=niceDate, scanDays=scanDays, todayStyle=todayStyle, wantYesterday=wantYesterday)
    w.doModal()
    del w

# vim: et
