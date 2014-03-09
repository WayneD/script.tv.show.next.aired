
How to use this addon in your skin:


I) Startup.xml:
RunScript(script.tv.show.next.aired,silent=True)

The script will scan your library and tries to fetch next aired info for every show.
There is no need to specify an alarm -- the script will will run a background update at regular intervals.

For shows that are airing today, the script will set the window properties listed below.

Window(Home).Property(NextAired.%d.*):
Label               (tv show name)
Thumb               (tv show icon)
AirTime             (eg. 'Wednesday, Thursday: 09:00 PM')
Path                (tv show path)
Library             (eg. videodb://2/2/1/ or videodb://tvshows/titles/1/)
Status              (eg. 'New Series'/'Returning Series'/'Cancelled/Ended')
StatusID            (ID of the status)
Network             (name of the tv network that's airing the show)
Started             (airdate of the first episode, eg. 09/24/07, 'Mon, Sep 24, 2007', etc.)
Classification      (type of show; N.B. not currently supported)
Genre               (genre of the show)
Premiered           (year the first episode was aired, eg. '1999')
Country             (production country of the tv show, eg. 'USA')
Runtime             (duration of the episode in minutes)
Fanart              (tv show fanart)
Today               (will return 'True' if the show is aired today, otherwise 'False')
NextDate            (date the next episode will be aired)
NextTitle           (name of the next episode)
NextNumber          (season/episode number of the next episode, eg. '04x01')
NextEpisodeNumber   (episode number of the next episode, eg. '04')
NextSeasonNumber    (season number of the next episode, eg. '01')
LatestDate          (date the last episode was aired)
LatestTitle         (name of the last episode)
LatestNumber        (season/episode number of the last episode)
LatestEpisodeNumber (episode number of the last episode)
LatestSeasonNumber  (season number of the last episode)
AirDay              (day(s) of the week the show is aired, eg 'Tuesday')
ShortTime           (time the show is aired, eg. '08:00 PM')
Art(poster)         (tv show poster)
Art(banner)         (tv show banner)
Art(fanart)         (tv show fanart)
Art(landscape)      (tv show landscape - artwork downloader required)
Art(clearlogo)      (tv show logo - artwork downloader required)
Art(clearart)       (tv show clearart - artwork downloader required)
Art(characterart)   (tv show characterart - artwork downloader required)

Status IDs:
0 - Returning Series
1 - Cancelled/Ended
2 - TBD/On The Bubble
4 - New Series
6 - Final Season
-1 - Undefined

---

Window(Home).Property(NextAired.*):
Total               (number of running shows)
TodayTotal          (number of shows aired today)
TodayShow           (list of shows aired today)


II) MyVideoNav.xml:
RunScript(script.tv.show.next.aired,backend=True)

the script will run in the background and provide next aired info for the focussed listitem.
the infolabels listed above are available, using this format:

Window(Home).Property(NextAired.*)


use !IsEmpty(Window(Home).Property(NextAired.NextDate)) as a visible condition!


example code:
<control type="group">
	<visible>!IsEmpty(Window(Home).Property(NextAired.NextDate))</visible>
	<control type="label">
		<posx>0</posx>
		<posy>0</posy>
		<width>800</width>
		<height>20</height>
		<label>$INFO[Window(Home).Property(NextAired.NextTitle)]</label>
	</control>
	<control type="label">
		<posx>0</posx>
		<posy>20</posy>
		<width>800</width>
		<height>20</height>
		<label>$INFO[Window(Home).Property(NextAired.NextDate)]</label>
	</control>
</control>



III) If you run the script without any options (or if it's started by the user),
the script will provide a TV Guide window.

This window is fully skinnable -- see script-NextAired-TVGuide.xml and
script-NextAired-TVGuide2.xml (the latter is the today-week guide).

A list of required IDs in script-NextAired-TVGuide.xml, which is selected if
the user has selected the traditional, Monday-week guide:

200 - container / shows aired on monday
201 - container / shows aired on tuesday
202 - container / shows aired on wednesday
203 - container / shows aired on thursday
204 - container / shows aired on friday
205 - container / shows aired on saturday
206 - container / shows aired on sunday
8 - in case all the containers above are empty, we set focus to this ID
(which is typically a settings-button of some kind).

If the user chooses to include more than 7 upcoming days (including today), then
episodes from the next week are included after this week's episodes for each
day.

A list of required IDs in script-NextAired-TVGuide2.xml, which is selected if
the user has selected the new, Today-week guide:

200 - container / shows aired Yesterday
201 - container / shows aired Today
202 - container / shows aired Today+1
203 - container / shows aired Today+2
204 - container / shows aired Today+3
205 - container / shows aired Today+4
206 - container / shows aired Today+5
207 - container / shows aired Today+6
208 - container / shows aired Today+7
209 - container / shows aired Today+8
210 - container / shows aired Today+9
211 - container / shows aired Today+10
212 - container / shows aired Today+11
213 - container / shows aired Today+12
214 - container / shows aired Today+13
215 - container / shows aired Today+14
8 - in case all the containers above are empty, we set focus to this ID.

If the user chooses to include fewer than the full 15 upcoming days (including
today) and/or to disable Yesterday, then the skin should be prepared to hide
the days that aren't enabled (the *.Wday and *.Date values below will be
empty for any disabled containers).

Various Window(home) vars that we provide (some are more useful in just one
of the 2 xml files, but all are always set):

Today's date:
    Window(home).Property(NextAired.TodayDate)

The date for the lists in dateshort format (Monday==1):
    Window(home).Property(NextAired.1.Date)
    ...
    Window(home).Property(NextAired.7.Date)

The day-of-the-week name for each container (not abbreviated), but the today-
week Guide gets a localized Yesterday and Today in place of 200 and 201:
    Window(home).Property(TVGuide.200.Wday)
    ...
    Window(home).Property(TVGuide.215.Wday)

The date for each container in a nice format (similar to datelong minus the
year, but with an abbreviated day-of-the-week name -- e.g. English looks like
"Mon, Feb 14"):
    Window(home).Property(TVGuide.200.Date)
    ...
    Window(home).Property(TVGuide.215.Date)

A list of available infolabels:
    ListItem.Label          (tv show name)
    ListItem.Thumb          (tv show thumb)
    ListItem.Property(*)    (see above)

Totals are available using the window properties listed above.

thumb type selected by the (0=poster, 1=banner, 2=logo):
    Window(home).Property(TVGuide.ThumbType)

Indicator for background fanart setting (1=enabled, empty if disabled):
    Window(home).Property(TVGuide.BackgroundFanart)

Indicator for 16:9-thumbs setting (1=enabled, empty if disabled):
    Window(home).Property(TVGuide.PreviewThumbs)

All other IDs and properties in the default script window are optional and not required by the script.


IV) To force an update of the nextaired database ahead of its next scheduled time:
RunScript(script.tv.show.next.aired,force=True)

To force an update as well as reset all the existing data (forcing a fresh scan of everything) use the reset option:
RunScript(script.tv.show.next.aired,reset=True)

The force update and reset options are also available in the addon settings.
