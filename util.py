#-------------------------------------------------------------------
# Filename: util.py
#  Purpose: Helper functions for ObsPyck
#   Author: Tobias Megies, Lion Krischer
#    Email: megies@geophysik.uni-muenchen.de
#  License: GPLv2
#
# Copyright (C) 2010 Tobias Megies, Lion Krischer
#---------------------------------------------------------------------

import os
import sys
import math
import platform
import shutil
import subprocess
import copy
import tempfile
import glob
import fnmatch
import warnings

import PyQt4
import numpy as np
import matplotlib as mpl
from matplotlib.colors import ColorConverter
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as QFigureCanvas
from matplotlib.widgets import MultiCursor as MplMultiCursor

from obspy.core import UTCDateTime
from obspy.core.event import StationMagnitude, StationMagnitudeContribution
try:
    from obspy.core.util import gps2DistAzimuth
except:
    from obspy.signal import gps2DistAzimuth
from obspy.core.event import Arrival, Pick

from obspy.core.util import getMatplotlibVersion
from obspy import fdsn
from obspy.taup.taup import getTravelTimes
from obspy.core.util import locations2degrees

mpl.rc('figure.subplot', left=0.05, right=0.98, bottom=0.10, top=0.92,
       hspace=0.28)
mpl.rcParams['font.size'] = 10


COMMANDLINE_OPTIONS = (
        # XXX wasn't working as expected
        #(("--debug"), {'dest': "debug", 'action': "store_true",
        #        'default': False,
        #        'help': "Switch on Ipython debugging in case of exception"}),
        (("-t", "--time"), {'dest': "time",
                'help': "Starttime of seismogram to retrieve. It takes a "
                "string which UTCDateTime can convert. E.g. "
                "'2010-01-10T05:00:00'"}),
        (("-d", "--duration"), {'type': "float", 'dest': "duration",
                'help': "Duration of seismogram in seconds"}),
        (("-f", "--files"), {'type': "string", 'dest': "files",
                'help': "Local files containing waveform data. List of "
                "absolute paths separated by commas"}),
        (("--dataless",), {'type': "string", 'dest': "dataless",
                'help': "Local Dataless SEED files to look up metadata for "
                "local waveform files. List of absolute paths separated by "
                "commas"}),
        (("-i", "--seishub-ids"), {'dest': "seishub_ids", 'default': "",
                'help': "Ids to retrieve from SeisHub. Star for channel and "
                "wildcards for stations are allowed, e.g. "
                "'BW.RJOB..EH*,BW.RM?*..EH*'"}),
        (("--seishub-servername",), {'dest': "seishub_servername",
                'default': 'teide',
                'help': "Servername of the SeisHub server"}),
        (("--seishub-port",), {'type': "int", 'dest': "seishub_port",
                'default': 8080, 'help': "Port of the SeisHub server"}),
        (("--seishub-user",), {'dest': "seishub_user", 'default': 'obspyck',
                'help': "Username for SeisHub server"}),
        (("--seishub-password",), {'dest': "seishub_password",
                'default': 'obspyck', 'help': "Password for SeisHub server"}),
        (("--seishub-timeout",), {'dest': "seishub_timeout", 'type': "int",
                'default': 10, 'help': "Timeout for SeisHub server"}),
        (("-k", "--keys"), {'action': "store_true", 'dest': "keybindings",
                'default': False, 'help': "Show keybindings and quit"}),
        (("--lowpass",), {'type': "float", 'dest': "lowpass", 'default': 20.0,
                'help': "Frequency for Lowpass-Slider"}),
        (("--highpass",), {'type': "float", 'dest': "highpass", 'default': 1.0,
                'help': "Frequency for Highpass-Slider"}),
        (("--sta",), {'type': "float", 'dest': "sta", 'default': 0.5,
                'help': "Window length for STA-Slider"}),
        (("--lta",), {'type': "float", 'dest': "lta", 'default': 10.0,
                'help': "Window length for LTA-Slider"}),
        (("--ar-f1",), {'type': "float", 'dest': "ar_f1",
                'default': 1.0, 'help': "Low corner frequency of AR picker"}),
        (("--ar-f2",), {'type': "float", 'dest': "ar_f2",
                'default': 20.0, 'help': "High corner frequency of AR picker"}),
        (("--ar-sta_p",), {'type': "float", 'dest': "ar_sta_p",
                'default': 0.1, 'help': "P STA window length of AR picker"}),
        (("--ar-lta_p",), {'type': "float", 'dest': "ar_lta_p",
                'default': 1.0, 'help': "P LTA window length of AR picker"}),
        (("--ar-sta_s",), {'type': "float", 'dest': "ar_sta_s",
                'default': 1.0, 'help': "S STA window length of AR picker"}),
        (("--ar-lta_s",), {'type': "float", 'dest': "ar_lta_s",
                'default': 4.0, 'help': "S LTA window length of AR picker"}),
        (("--ar-m_p",), {'type': "int", 'dest': "ar_m_p",
                'default': 2, 'help': "number of coefficients for P of AR picker"}),
        (("--ar-m_s",), {'type': "int", 'dest': "ar_m_s",
                'default': 8, 'help': "number of coefficients for S of AR picker"}),
        (("--ar-l_p",), {'type': "float", 'dest': "ar_l_p",
                'default': 0.1, 'help': "variance window length for P of AR picker"}),
        (("--ar-l_s",), {'type': "float", 'dest': "ar_l_s",
                'default': 0.2, 'help': "variance window length for S of AR picker"}),
        (("--nozeromean",), {'action': "store_true", 'dest': "nozeromean",
                'default': False,
                'help': "Deactivate offset removal of traces"}),
        (("--nonormalization",), {'action': "store_true",
                'dest': "nonormalization", 'default': False,
                'help': "Deactivate normalization to nm/s for plotting " + \
                "using overall sensitivity (tr.stats.paz.sensitivity)"}),
        (("--nometadata",), {'action': "store_true",
                'dest': "nometadata", 'default': False,
                'help': "Deactivate fetching/parsing metadata for waveforms"}),
        (("--noevents",), {'action': "store_true",
                'dest': "noevents", 'default': False,
                'help': "Deactivate fetching event data using FDSNWS and plotting theoretical arrivals."}),
        (("--pluginpath",), {'dest': "pluginpath",
                'default': "/baysoft/obspyck/",
                'help': "Path to local directory containing the folders with "
                "the files for the external programs. Large files/folders "
                "should only be linked in this directory as the contents are "
                "copied to a temporary directory (links are preserved)."}),
        (("-o", "--starttime-offset"), {'type': "float", 'dest': "starttime_offset",
                'default': 0.0, 'help': "Offset to add to specified starttime "
                "in seconds. Thus a time from an automatic picker can be used "
                "with a specified offset for the starttime. E.g. to request a "
                "waveform starting 30 seconds earlier than the specified time "
                "use -30."}),
        (("-m", "--merge"), {'type': "choice", 'dest': "merge", 'default': "",
                'choices': ("", "safe", "overwrite"),
                'help': "After fetching the streams run a merge "
                "operation on every stream. If not done, streams with gaps "
                "and therefore more traces per channel get discarded.\nTwo "
                "methods are supported (see http://docs.obspy.org/packages/"
                "auto/obspy.core.trace.Trace.__add__.html  for details)\n  "
                "\"safe\": overlaps are discarded "
                "completely\n  \"overwrite\": the second trace is used for "
                "overlapping parts of the trace"}),
        (("--arclink-ids",), {'dest': "arclink_ids", 'default': '',
                'help': "Ids to retrieve via arclink, star for channel "
                "is allowed, e.g. 'BW.RJOB..EH*,BW.ROTZ..EH*'"}),
        (("--arclink-servername",), {'dest': "arclink_servername",
                'default': 'webdc.eu',
                'help': "Servername of the arclink server"}),
        (("--arclink-port",), {'type': "int", 'dest': "arclink_port",
                'default': 18001, 'help': "Port of the arclink server"}),
        (("--arclink-user",), {'dest': "arclink_user", 'default': 'Anonymous',
                'help': "Username for arclink server"}),
        (("--arclink-password",), {'dest': "arclink_password", 'default': '',
                'help': "Password for arclink server"}),
        (("--arclink-institution",), {'dest': "arclink_institution",
                'default': 'Anonymous',
                'help': "Password for arclink server"}),
        (("--arclink-timeout",), {'dest': "arclink_timeout", 'type': "int",
                'default': 20, 'help': "Timeout for arclink server"}),
        (("--ignore-chksum",), {'action': "store_false", 'dest': "verify_chksum",
                                'default': True,
                                'help': "Deactivate chksum check for local GSE2 files"}),
        (("--verbosity",), {'dest': "verbosity",
                            'default': "normal",
                            'help': ("Control verbosity of info window. "
                                     "Possible values: "
                                     "'normal' (default), 'verbose', "
                                     "'debug', 'quiet'")}),
        (("--filter",), {'action': "store_true", 'dest': "filter",
                'default': False,
                'help': "Switch filter button on at startup."}))
PROGRAMS = {
        'nlloc': {'filenames': {'exe': "NLLoc", 'phases': "nlloc.obs",
                                'summary': "nlloc.hyp",
                                'scatter': "nlloc.scat"}},
        'hyp_2000': {'filenames': {'exe': "hyp2000",'control': "bay2000.inp",
                                   'phases': "hyp2000.pha",
                                   'stations': "stations.dat",
                                   'summary': "hypo.prt"}},
        'focmec': {'filenames': {'exe': "rfocmec", 'phases': "focmec.dat",
                                 'stdout': "focmec.stdout",
                                 'summary': "focmec.out"}}}
SEISMIC_PHASES = ('P', 'S')
PHASE_COLORS = {'P': "red", 'S': "blue", 'Mag': "green"}
COMPONENT_COLORS = {'Z': "k", 'N': "b", 'E': "r"}
PHASE_LINESTYLES = {'P': "-", 'S': "-", 'Psynth': "--", 'Ssynth': "--",
        'PErr1': "-", 'PErr2': "-", 'SErr1': "-", 'SErr2': "-"}
PHASE_LINEHEIGHT_PERC = {'P': 1, 'S': 1, 'Psynth': 1, 'Ssynth': 1,
        'PErr1': 0.75, 'PErr2': 0.75, 'SErr1': 0.75, 'SErr2': 0.75}
KEY_FULLNAMES = {'P': "P pick", 'Psynth': "synthetic P pick",
        'PWeight': "P pick weight", 'PPol': "P pick polarity",
        'POnset': "P pick onset", 'PErr1': "left P error pick",
        'PErr2': "right P error pick", 'S': "S pick",
        'Ssynth': "synthetic S pick", 'SWeight': "S pick weight",
        'SPol': "S pick polarity", 'SOnset': "S pick onset",
        'SErr1': "left S error pick", 'SErr2': "right S error pick",
        'MagMin1': "Magnitude minimum estimation pick",
        'MagMax1': "Magnitude maximum estimation pick",
        'MagMin2': "Magnitude minimum estimation pick",
        'MagMax2': "Magnitude maximum estimation pick"}
WIDGET_NAMES = ("qToolButton_clearAll", "qToolButton_clearOrigMag",
        "qToolButton_clearFocMec", "qToolButton_doHyp2000",
        "qToolButton_doNlloc", "qComboBox_nllocModel",
        "qToolButton_doFocMec", "qToolButton_showMap",
        "qToolButton_showFocMec", "qToolButton_nextFocMec",
        "qToolButton_showWadati", "qToolButton_getNextEvent",
        "qToolButton_updateEventList", "qToolButton_sendNewEvent",
        "qToolButton_replaceEvent",
        "qToolButton_deleteEvent", "qCheckBox_public",
        "qCheckBox_sysop", "qLineEdit_sysopPassword", "qComboBox_eventType",
        "qToolButton_previousStream", "qLabel_streamNumber",
        "qComboBox_streamName", "qToolButton_nextStream",
        "qToolButton_overview", "qComboBox_phaseType", "qToolButton_rotateLQT",
        "qToolButton_rotateZRT", "qToolButton_filter", "qToolButton_trigger",
        "qToolButton_arpicker", "qComboBox_filterType", "qCheckBox_zerophase",
        "qLabel_highpass", "qDoubleSpinBox_highpass", "qLabel_lowpass",
        "qDoubleSpinBox_lowpass",
        "qDoubleSpinBox_corners", "qLabel_corners", "qCheckBox_50Hz",
        "qTextEdit_qml", "qPushButton_qml_update",
        "qLabel_sta", "qDoubleSpinBox_sta",
        "qLabel_lta", "qDoubleSpinBox_lta", "qToolButton_spectrogram",
        "qCheckBox_spectrogramLog", "qLabel_wlen", "qDoubleSpinBox_wlen",
        "qLabel_perlap", "qDoubleSpinBox_perlap", "qPlainTextEdit_stdout",
        "qPlainTextEdit_stderr")
#Estimating the maximum/minimum in a sample-window around click
MAG_PICKWINDOW = 10
MAG_MARKER = {'marker': (8, 2, 0), 'edgewidth': 1.8, 'size': 20}
AXVLINEWIDTH = 1.5
# dictionary for key-bindings.
KEYS = {'setPick': "a", 'setPickError': "s", 'delPick': "q",
        'setMagMin': "a", 'setMagMax': "s", 'delMagMinMax': "q",
        'switchPhase': "control",
        'prevStream': "y", 'nextStream': "x", 'switchWheelZoomAxis': "shift",
        'setWeight': {'0': 0, '1': 1, '2': 2, '3': 3},
        'setPol': {'u': "positive", 'd': "negative", '-': "negative",
                   '+': "positive"},
        'setOnset': {'i': "impulsive", 'e': "emergent"}}
# XXX Qt:
#KEYS = {'setPick': "Key_A", 'setPickError': "Key_S", 'delPick': "Key_Q",
#        'setMagMin': "Key_A", 'setMagMax': "Key_S", 'delMagMinMax': "Key_Q",
#        'switchPhase': "Key_Control",
#        'prevStream': "Key_Y", 'nextStream': "Key_X", 'switchWheelZoomAxis': "Key_Shift",
#        'setWeight': {'Key_0': 0, 'Key_1': 1, 'Key_2': 2, 'Key_3': 3},
#        'setPol': {'Key_U': "up", 'Key_D': "down", 'Key_Plus': "poorup", 'Key_Minus': "poordown"},
#        'setOnset': {'Key_I': "impulsive", 'Key_E': "emergent"}}

ROTATE_LQT_COMP_MAP = {"Z": "L", "N": "Q", "E": "T"}
ROTATE_ZRT_COMP_MAP = {"Z": "Z", "N": "R", "E": "T"}
S_POL_MAP_ZRT = {'R': {'up': "forward", 'down': "backward",
                       'poorup': "forward", 'poordown': "backward"},
                 'T': {'up': "right", 'down': "left",
                       'poorup': "right", 'poordown': "left"}}
S_POL_PHASE_TYPE = {'R': "SV", 'T': "SH"}
POLARITY_2_FOCMEC = {'Z': {'positive': "U", 'negative': "D"},
                     'R': {'positive': "F", 'negative': "B"},
                     'T': {'positive': "R", 'negative': "L"}}

# only strings involved, so shallow copy is fine
POLARITY_CHARS = {'positive': "+", 'negative': "-", 'undecidable': "?",
                  None: "_"}
ONSET_CHARS = {'impulsive': "I", 'emergent': "E", 'questionable': "?",
               None: "_"}
LOGLEVELS = {'normal': "CRITICAL", 'verbose': "INFO", 'debug': "DEBUG",
             'quiet': 100}

ONE_SIGMA = 68.3
TWO_SIGMA = 95.4

NOT_REIMPLEMENTED_MSG = ("Feature was not reimplemented after major "
                         "change to QuakeML.")

class QMplCanvas(QFigureCanvas):
    """
    Class to represent the FigureCanvas widget.
    """
    def __init__(self, parent=None):
        # Standard Matplotlib code to generate the plot
        self.fig = Figure()
        # initialize the canvas where the Figure renders into
        QFigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

def matplotlib_color_to_rgb(color):
    """
    Converts matplotlib colors to rgb.
    """
    rgb = ColorConverter().to_rgb(color)
    return [int(_i*255) for _i in rgb]

def check_keybinding_conflicts(keys):
    """
    check for conflicting keybindings. 
    we have to check twice, because keys for setting picks and magnitudes
    are allowed to interfere...
    """
    for ignored_key_list in [['setMagMin', 'setMagMax', 'delMagMinMax'],
                             ['setPick', 'setPickError', 'delPick']]:
        tmp_keys = copy.deepcopy(keys)
        tmp_keys2 = {}
        for ignored_key in ignored_key_list:
            tmp_keys.pop(ignored_key)
        while tmp_keys:
            key, item = tmp_keys.popitem()
            if isinstance(item, dict):
                while item:
                    k, v = item.popitem()
                    tmp_keys2["_".join([key, str(v)])] = k
            else:
                tmp_keys2[key] = item
        if len(set(tmp_keys2.keys())) != len(set(tmp_keys2.values())):
            err = "Interfering keybindings. Please check variable KEYS"
            raise Exception(err)

def fetch_waveforms_with_metadata(options):
    """
    Sets up obspy clients and fetches waveforms and metadata according to command
    line options.
    Now also fetches data via arclink if --arclink-ids is used.
    XXX Notes: XXX
     - there is a problem in the arclink client with duplicate traces in
       fetched streams. therefore at the moment it might be necessary to use
       "-m overwrite" option.

    :returns: (dictionary with clients,
               list(:class:`obspy.core.stream.Stream`s))
    """
    getPAZ = not options.nometadata
    getCoordinates = not options.nometadata
    t1 = UTCDateTime(options.time) + options.starttime_offset
    t2 = t1 + options.duration
    streams = []
    clients = {}
    sta_fetched = set()
    # Local files:
    parsers = []
    if options.dataless:
        from obspy.xseed import Parser
        print "=" * 80
        print "Reading local dataless files:"
        print "-" * 80
        for file in options.dataless.split(","):
            print file
            parsers.append(Parser(file))
    if options.files:
        from obspy import read, Stream
        stream_tmp = Stream()
        print "=" * 80
        print "Reading local waveform files:"
        print "-" * 80
        for file in options.files.split(","):
            print file
            st = read(file, starttime=t1, endtime=t2, verify_chksum=options.verify_chksum)
            for tr in st:
                if not options.nometadata:
                    for parser in parsers:
                        try:
                            tr.stats.paz = parser.getPAZ(tr.id, tr.stats.starttime)
                            tr.stats.coordinates = parser.getCoordinates(tr.id, tr.stats.starttime)
                            break
                        except:
                            continue
                        print "found no metadata for %s!!!" % file
                if tr.stats._format == 'GSE2':
                    apply_gse2_calib(tr)
            stream_tmp += st
        ids = set([(tr.stats.network, tr.stats.station, tr.stats.location) for tr in stream_tmp])
        for net, sta, loc in ids:
            streams.append(stream_tmp.select(network=net, station=sta, location=loc))
    # SeisHub
    if options.seishub_ids:
        from obspy.seishub import Client
        print "=" * 80
        print "Fetching waveforms and metadata from SeisHub:"
        print "-" * 80
        baseurl = "http://" + options.seishub_servername + ":%i" % options.seishub_port
        client = Client(base_url=baseurl, user=options.seishub_user,
                        password=options.seishub_password, timeout=options.seishub_timeout)
        for id in options.seishub_ids.split(","):
            net, sta_wildcard, loc, cha = id.split(".")
            stations_to_fetch = []
            if any([char in sta_wildcard for char in "*?[]"]):
                for sta in sorted(client.waveform.getStationIds(network=net)):
                    if fnmatch.fnmatch(sta, sta_wildcard):
                        stations_to_fetch.append(sta)
            else:
                stations_to_fetch = [sta_wildcard]
            for sta in stations_to_fetch:
                # make sure we dont fetch a single station of
                # one network twice (could happen with wildcards)
                net_sta = "%s.%s" % (net, sta)
                if net_sta in sta_fetched:
                    print "%s skipped! (Was already retrieved)" % net_sta.ljust(8)
                    continue
                try:
                    sys.stdout.write("\r%s ..." % net_sta.ljust(8))
                    sys.stdout.flush()
                    st = client.waveform.getWaveform(net, sta, loc, cha, t1,
                            t2, apply_filter=True, getPAZ=getPAZ,
                            getCoordinates=getCoordinates)
                    sta_fetched.add(net_sta)
                    sys.stdout.write("\r%s fetched.\n" % net_sta.ljust(8))
                    sys.stdout.flush()
                except Exception, e:
                    sys.stdout.write("\r%s skipped! (Server replied: %s)\n" % (net_sta.ljust(8), e))
                    sys.stdout.flush()
                    continue
                for tr in st:
                    if tr.stats._format == 'GSE2':
                        apply_gse2_calib(tr)
                    tr.stats['_format'] = "SeisHub"
                streams.append(st)
        clients['SeisHub'] = client
    # ArcLink
    if options.arclink_ids:
        from obspy.arclink import Client
        print "=" * 80
        print "Fetching waveforms and metadata via ArcLink:"
        print "-" * 80
        client = Client(host=options.arclink_servername,
                        port=options.arclink_port,
                        timeout=options.arclink_timeout,
                        user=options.arclink_user,
                        password=options.arclink_password,
                        institution=options.arclink_institution)
        for id in options.arclink_ids.split(","):
            net, sta, loc, cha = id.split(".")
            net_sta = "%s.%s" % (net, sta)
            if net_sta in sta_fetched:
                print "%s skipped! (Was already retrieved)" % net_sta.ljust(8)
                continue
            try:
                sys.stdout.write("\r%s ..." % net_sta.ljust(8))
                sys.stdout.flush()
                st = client.getWaveform(network=net, station=sta,
                                        location=loc, channel=cha,
                                        starttime=t1, endtime=t2,
                                        getPAZ=getPAZ, getCoordinates=getCoordinates)
                sta_fetched.add(net_sta)
                sys.stdout.write("\r%s fetched.\n" % net_sta.ljust(8))
                sys.stdout.flush()
            except Exception, e:
                sys.stdout.write("\r%s skipped! (Server replied: %s)\n" % (net_sta.ljust(8), e))
                sys.stdout.flush()
                continue
            for tr in st:
                tr.stats['_format'] = "ArcLink"
            streams.append(st)
        clients['ArcLink'] = client
    print "=" * 80
    return (clients, streams)

def merge_check_and_cleanup_streams(streams, options):
    """
    Cleanup given list of streams so that they conform with what ObsPyck
    expects.

    Conditions:
    - either one Z or three ZNE traces
    - no two streams for any station (of same network)
    - no streams with traces of different stations

    :returns: (warn_msg, merge_msg, list(:class:`obspy.core.stream.Stream`s))
    """
    # we need to go through streams/dicts backwards in order not to get
    # problems because of the pop() statement
    warn_msg = ""
    merge_msg = ""
    # Merge on every stream if this option is passed on command line:
    for st in streams:
        st.merge(method=-1)
    if options.merge:
        if options.merge.lower() == "safe":
            for st in streams:
                st.merge(method=0)
        elif options.merge.lower() == "overwrite":
            for st in streams:
                if st.getGaps() and max([gap[-1] for gap in st.getGaps()]) < 5:
                    msg = 'Interpolated over gap(s) with less than 5 ' + \
                          'samples for station: %s.%s'
                    msg = msg % (st[0].stats.network, st[0].stats.station)
                    warn_msg += msg + "\n"
                    st.merge(method=1, fill_value="interpolate")
                else:
                    st.merge(method=1)
        else:
            err = "Unrecognized option for merging traces. Try " + \
                  "\"safe\" or \"overwrite\"."
            raise Exception(err)

    # Sort streams again, if there was a merge this could be necessary 
    for st in streams:
        st.sort(reverse=True)
    sta_list = set()
    # XXX we need the list() because otherwise the iterator gets garbled if
    # XXX removing streams inside the for loop!!
    for st in list(streams):
        # check for streams with mixed stations/networks and remove them
        if len(st) != len(st.select(network=st[0].stats.network,
                                    station=st[0].stats.station)):
            msg = "Warning: Stream with a mix of stations/networks. " + \
                  "Discarding stream."
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        net_sta = "%s.%s" % (st[0].stats.network.strip(),
                             st[0].stats.station.strip())
        # Here we make sure that a station/network combination is not
        # present with two streams.
        if net_sta in sta_list:
            msg = "Warning: Station/Network combination \"%s\" " + \
                  "already in stream list. Discarding stream." % net_sta
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        if len(st) not in [1, 3]:
            msg = 'Warning: All streams must have either one Z trace ' + \
                  'or a set of three ZNE traces.'
            print msg
            warn_msg += msg + "\n"
            # remove all unknown channels ending with something other than
            # Z/N/E and try again...
            removed_channels = ""
            for tr in st:
                if tr.stats.channel[-1] not in ["Z", "N", "E"]:
                    removed_channels += " " + tr.stats.channel
                    st.remove(tr)
            if len(st.traces) in [1, 3]:
                msg = 'Warning: deleted some unknown channels in ' + \
                      'stream %s.%s' % (net_sta, removed_channels)
                print msg
                warn_msg += msg + "\n"
                continue
            else:
                msg = 'Stream %s discarded.\n' % net_sta + \
                      'Reason: Number of traces != (1 or 3)'
                print msg
                warn_msg += msg + "\n"
                #for j, tr in enumerate(st.traces):
                #    msg = 'Trace no. %i in Stream: %s\n%s' % \
                #            (j + 1, tr.stats.channel, tr.stats)
                msg = str(st)
                print msg
                warn_msg += msg + "\n"
                streams.remove(st)
                merge_msg = '\nIMPORTANT:\nYou can try the command line ' + \
                        'option merge (-m safe or -m overwrite) to ' + \
                        'avoid losing streams due gaps/overlaps.'
                continue
        if len(st) == 1 and st[0].stats.channel[-1] != 'Z':
            msg = 'Warning: All streams must have either one Z trace ' + \
                  'or a set of three ZNE traces.'
            msg += 'Stream %s discarded. Reason: ' % net_sta + \
                   'Exactly one trace present but this is no Z trace'
            print msg
            warn_msg += msg + "\n"
            #for j, tr in enumerate(st.traces):
            #    msg = 'Trace no. %i in Stream: %s\n%s' % \
            #            (j + 1, tr.stats.channel, tr.stats)
            msg = str(st)
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        if len(st) == 3 and (st[0].stats.channel[-1] != 'Z' or
                             st[1].stats.channel[-1] != 'N' or
                             st[2].stats.channel[-1] != 'E'):
            msg = 'Warning: All streams must have either one Z trace ' + \
                  'or a set of three ZNE traces.'
            msg += 'Stream %s discarded. Reason: ' % net_sta + \
                   'Exactly three traces present but they are not ZNE'
            print msg
            warn_msg += msg + "\n"
            #for j, tr in enumerate(st.traces):
            #    msg = 'Trace no. %i in Stream: %s\n%s' % \
            #            (j + 1, tr.stats.channel, tr.stats)
            msg = str(st)
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        sta_list.add(net_sta)
    # demean traces if not explicitly deactivated on command line
    if not options.nozeromean:
        for st in streams:
            try:
                st.detrend('simple')
                st.detrend('constant')
            except NotImplementedError as e:
                if "Trace with masked values found." in e.message:
                    msg = 'Detrending/demeaning not possible for station ' + \
                          '(masked Traces): %s' % net_sta
                    warn_msg += msg + "\n"
                else:
                    raise
    return (warn_msg, merge_msg, streams)


def cleanup_streams(streams, options):
    """
    Function to remove streams that do not provide the necessary metadata.

    :returns: (list(:class:`obspy.core.stream.Stream`s),
               list(dict))
    """
    # we need to go through streams/dicts backwards in order not to get
    # problems because of the pop() statement
    for i in range(len(streams))[::-1]:
        st = streams[i]
        trZ = st.select(component="Z")[0]
        if len(st) == 3:
            trN = st.select(component="N")[0]
            trE = st.select(component="E")[0]
        sta = trZ.stats.station.strip()
        net = trZ.stats.network.strip()
        if not options.nometadata:
            try:
                trZ.stats.coordinates.get("longitude")
                trZ.stats.coordinates.get("latitude")
                trZ.stats.coordinates.get("elevation")
                trZ.stats.get("paz")
                if len(st) == 3:
                    trN.stats.get("paz")
                    trE.stats.get("paz")
            except:
                print 'Error: Missing metadata for %s.%s. Discarding stream.' \
                    % (net, sta)
                streams.pop(i)
                continue
    return streams

def setup_external_programs(options):
    """
    Sets up temdir, copies program files, fills in PROGRAMS dict, sets up
    system calls for programs.
    Depends on command line options, returns temporary directory.

    :param options: Command line options of ObsPyck
    :type options: options as returned by :meth:`optparse.OptionParser.parse_args`
    :returns: String representation of temporary directory with program files.
    """
    if not os.path.isdir(options.pluginpath):
        msg = "No such directory: '%s'" % options.pluginpath
        raise IOError(msg)
    tmp_dir = tempfile.mkdtemp(prefix="obspyck-")
    # set binary names to use depending on architecture and platform...
    env = os.environ
    architecture = platform.architecture()[0]
    system = platform.system()
    global SHELL
    if system == "Windows":
        SHELL = True
    else:
        SHELL = False
    # Setup external programs #############################################
    for prog_basename, prog_dict in PROGRAMS.iteritems():
        prog_srcpath = os.path.join(options.pluginpath, prog_basename)
        prog_tmpdir = os.path.join(tmp_dir, prog_basename)
        prog_dict['dir'] = prog_tmpdir
        shutil.copytree(prog_srcpath, prog_tmpdir, symlinks=True)
        prog_dict['files'] = {}
        for key, filename in prog_dict['filenames'].iteritems():
            prog_dict['files'][key] = os.path.join(prog_tmpdir, filename)
        prog_dict['files']['exe'] = "__".join(\
                [prog_dict['filenames']['exe'], system, architecture])
        # setup clean environment
        prog_dict['env'] = {}
        prog_dict['env']['PATH'] = prog_dict['dir'] + os.pathsep + env['PATH']
        if 'SystemRoot' in env:
            prog_dict['env']['SystemRoot'] = env['SystemRoot']
    # Hyp2000 #############################################################
    prog_dict = PROGRAMS['hyp_2000']
    prog_dict['env']['HYP2000_DATA'] = prog_dict['dir'] + os.sep
    def tmp(prog_dict):
        files = prog_dict['files']
        for file in [files['phases'], files['stations'], files['summary']]:
            if os.path.isfile(file):
                os.remove(file)
        return
    prog_dict['PreCall'] = tmp
    def tmp(prog_dict):
        sub = subprocess.Popen(prog_dict['files']['exe'], shell=SHELL,
                cwd=prog_dict['dir'], env=prog_dict['env'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        input = open(prog_dict['files']['control'], "rt").read()
        (msg, err) = sub.communicate(input)
        if system == "Darwin":
            returncode = sub.returncode
        else:
            returncode = sub.wait()
        return (msg, err, returncode)
    prog_dict['Call'] = tmp
    # NLLoc ###############################################################
    prog_dict = PROGRAMS['nlloc']
    def tmp(prog_dict):
        filepattern = os.path.join(prog_dict['dir'], "nlloc*")
        print filepattern
        for file in glob.glob(filepattern):
            os.remove(file)
        return
    prog_dict['PreCall'] = tmp
    def tmp(prog_dict, controlfilename):
        sub = subprocess.Popen([prog_dict['files']['exe'], controlfilename],
                cwd=prog_dict['dir'], env=prog_dict['env'], shell=SHELL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if system == "Darwin":
            returncode = sub.returncode
        else:
            returncode = sub.wait()
        msg = "".join(sub.stdout.readlines())
        err = "".join(sub.stderr.readlines())
        for pattern, key in [("nlloc.*.*.*.loc.scat", 'scatter'),
                             ("nlloc.*.*.*.loc.hyp", 'summary')]:
            pattern = os.path.join(prog_dict['dir'], pattern)
            newname = os.path.join(prog_dict['dir'], prog_dict['files'][key])
            for file in glob.glob(pattern):
                os.rename(file, newname)
        return (msg, err, returncode)
    prog_dict['Call'] = tmp
    # focmec ##############################################################
    prog_dict = PROGRAMS['focmec']
    def tmp(prog_dict):
        sub = subprocess.Popen(prog_dict['files']['exe'], shell=SHELL,
                cwd=prog_dict['dir'], env=prog_dict['env'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if system == "Darwin":
            returncode = sub.returncode
        else:
            returncode = sub.wait()
        msg = "".join(sub.stdout.readlines())
        err = "".join(sub.stderr.readlines())
        return (msg, err, returncode)
    prog_dict['Call'] = tmp
    #######################################################################
    return tmp_dir

#Monkey patch (need to remember the ids of the mpl_connect-statements to remove them later)
#See source: http://matplotlib.sourcearchive.com/documentation/0.98.1/widgets_8py-source.html
class MultiCursor(MplMultiCursor):
    def __init__(self, canvas, axes, useblit=True, **lineprops):
        if hasattr(self, "id1"):
            self.canvas.mpl_disconnect(self.id1)
            self.canvas.mpl_disconnect(self.id2)
        self.canvas = canvas
        self.axes = axes
        xmin, xmax = axes[-1].get_xlim()
        xmid = 0.5*(xmin+xmax)
        self.hlines = []
        self.vlines = []
        self.horizOn = False
        self.vertOn = True
        self.lines = [ax.axvline(xmid, visible=False, **lineprops) for ax in axes]
        self.visible = True
        self.useblit = useblit
        self.background = None
        self.needclear = False
        self.id1 = self.canvas.mpl_connect('motion_notify_event', self.onmove)
        self.id2 = self.canvas.mpl_connect('draw_event', self.clear)

    @property
    def lines(self):
        if getMatplotlibVersion() < [1, 3, 0]:
            return self.__dict__["lines"]
        else:
            return self.vlines

    @lines.setter
    def lines(self, value):
        if getMatplotlibVersion() < [1, 3, 0]:
            self.__dict__["lines"] = value
        else:
            self.vlines = value


#def gk2lonlat(x, y, m_to_km=True):
    """
    This function converts X/Y Gauss-Krueger coordinates (zone 4, central
    meridian 12 deg) to Longitude/Latitude in WGS84 reference ellipsoid.
    We do this using pyproj (python bindings for proj4) which can be installed
    using 'easy_install pyproj' from pypi.python.org.
    Input can be single coordinates or coordinate lists/arrays.
    
    Useful Links:
    http://pyproj.googlecode.com/svn/trunk/README.html
    http://trac.osgeo.org/proj/
    http://www.epsg-registry.org/
    """
#    import pyproj

#    proj_wgs84 = pyproj.Proj(init="epsg:4326")
#    proj_gk4 = pyproj.Proj(init="epsg:31468")
#    # convert to meters first
#    if m_to_km:
#        x = x * 1000.
#        y = y * 1000.
#    lon, lat = pyproj.transform(proj_gk4, proj_wgs84, x, y)
#    return (lon, lat)

    

def lonlatconv(x, y):
    lat = -37 +(y/111.111)
    lon = 144+ (x/(111.111*math.cos(math.radians(-37.346500347))))
    return (lon, lat)

def readNLLocScatter(scat_filename, textviewStdErrImproved):
    """
    This function reads location and values of pdf scatter samples from the
    specified NLLoc *.scat binary file (type "<f4", 4 header values, then 4
    floats per sample: x, y, z, pdf value) and converts X/Y Gauss-Krueger
    coordinates (zone 4, central meridian 12 deg) to Longitude/Latitude in
    WGS84 reference ellipsoid.
    Messages on stderr are written to specified GUI textview.
    Returns an array of xy pairs.
    """
    # read data, omit the first 4 values (header information) and reshape
    data = np.fromfile(scat_filename, dtype="<f4").astype("float")[4:]
    data = data.reshape((len(data)/4, 4)).swapaxes(0, 1)
    #lon, lat = gk2lonlat(data[0], data[1])
    lon, lat = lonlatconv(data[0], data[1])
    return np.vstack((lon, lat, data[2]))

def errorEllipsoid2CartesianErrors(azimuth1, dip1, len1, azimuth2, dip2, len2,
                                   len3):
    """
    This method converts the location error of NLLoc given as the 3D error
    ellipsoid (two azimuths, two dips and three axis lengths) to a cartesian
    representation.
    We calculate the cartesian representation of each of the ellipsoids three
    eigenvectors and use the maximum of these vectors components on every axis.
    """
    z = len1 * np.sin(np.radians(dip1))
    xy = len1 * np.cos(np.radians(dip1))
    x = xy * np.sin(np.radians(azimuth1))
    y = xy * np.cos(np.radians(azimuth1))
    v1 = np.array([x, y, z])

    z = len2 * np.sin(np.radians(dip2))
    xy = len2 * np.cos(np.radians(dip2))
    x = xy * np.sin(np.radians(azimuth2))
    y = xy * np.cos(np.radians(azimuth2))
    v2 = np.array([x, y, z])

    v3 = np.cross(v1, v2)
    v3 /= np.sqrt(np.dot(v3, v3))
    v3 *= len3

    v1 = np.abs(v1)
    v2 = np.abs(v2)
    v3 = np.abs(v3)

    error_x = max([v1[0], v2[0], v3[0]])
    error_y = max([v1[1], v2[1], v3[1]])
    error_z = max([v1[2], v2[2], v3[2]])
    
    return (error_x, error_y, error_z)

def formatXTicklabels(x, *pos):
    """
    Make a nice formatting for y axis ticklabels: minutes:seconds.microsec
    """
    # x is of type numpy.float64, the string representation of that float
    # strips of all tailing zeros
    # pos returns the position of x on the axis while zooming, None otherwise
    min = int(x / 60.)
    if min > 0:
        sec = x % 60
        return "%i:%06.3f" % (min, sec)
    else:
        return "%.3f" % x

def map_qKeys(key_dict):
    """
    Map Dictionary of form {'functionality': "Qt_Key_name"} to
    {'functionality': Qt_Key_Code} for use in check against event Keys.

    >>> KEYS = {'delMagMinMax': 'Key_Escape',
    ...         'delPick': 'Key_Escape',
    ...         'nextStream': 'Key_X',
    ...         'prevStream': 'Key_Y',
    ...         'setPol': {'Key_D': 'down',
    ...                    'Key_Minus': 'poordown',
    ...                    'Key_Plus': 'poorup',
    ...                    'Key_U': 'up'},
    ...         'setWeight': {'Key_0': 0, 'Key_1': 1, 'Key_2': 2, 'Key_3': 3},
    ...         'switchWheelZoomAxis': 'Key_Shift'}
    >>> map_qKeys(KEYS)
    {'delMagMinMax': 16777216,
     'delPick': 16777216,
     'nextStream': 88,
     'prevStream': 89,
     'setPol': {43: 'poorup', 45: 'poordown', 68: 'down', 85: 'up'},
     'setWeight': {48: 0, 49: 1, 50: 2, 51: 3},
     'switchWheelZoomAxis': 16777248}
    """
    Qt = PyQt4.QtCore.Qt
    for functionality, key_name in key_dict.iteritems():
        if isinstance(key_name, str):
            key_dict[functionality] = getattr(Qt, key_name)
        # sometimes we get a nested dictionary (e.g. "setWeight")...
        elif isinstance(key_name, dict):
            nested_dict = key_name
            new = {}
            for key_name, value in nested_dict.iteritems():
                new[getattr(Qt, key_name)] = value
            key_dict[functionality] = new
    return key_dict

def coords2azbazinc(stream, origin):
    """
    Returns azimuth, backazimuth and incidence angle from station coordinates
    given in first trace of stream and from event location specified in origin
    dictionary.
    """
    sta_coords = stream[0].stats.coordinates
    dist, bazim, azim = gps2DistAzimuth(sta_coords.latitude,
            sta_coords.longitude, float(origin.latitude),
            float(origin.longitude))
    elev_diff = sta_coords.elevation - float(origin.depth)
    inci = math.atan2(dist, elev_diff) * 180.0 / math.pi
    return azim, bazim, inci

class SplitWriter():
    """
    Implements a write method that writes a given message on all children
    """
    def __init__(self, *objects):
        """
        Remember provided objects as children.
        """
        self.children = objects

    def write(self, msg):
        """
        Sends msg to all childrens write method.
        """
        for obj in self.children:
            if isinstance(obj, PyQt4.QtGui.QPlainTextEdit):
                if msg == '\n':
                    return
                if msg.endswith('\n'):
                    msg_ = msg[:-1]
                else:
                    msg_ = msg
                obj.appendPlainText(msg_)
            else:
                obj.write(msg)


def getArrivalForPick(arrivals, pick):
    """
    searches given arrivals for an arrival that references the given
    pick and returns it (empty Arrival object otherwise).
    """
    arrival = None
    for a in arrivals:
        if a.pick_id == pick.resource_id:
            arrival = a
            break
    return arrival


def getPickForArrival(picks, arrival):
    """
    searches list of picks for a pick that matches the arrivals pick_id
    and returns it (empty Pick object otherwise).
    """
    pick = None
    for p in picks:
        if arrival.pick_id == p.resource_id:
            pick = p
            break
    return pick


def get_event_info(starttime, endtime, streams):
    events = []
    arrivals = {}
    try:
        client = fdsn.Client("NERIES")
        events = client.get_events(starttime=starttime - 20 * 60,
                                   endtime=endtime)
        for ev in events[::-1]:
            has_arrivals = False
            origin = ev.origins[0]
            origin_time = origin.time
            lon1 = origin.longitude
            lat1 = origin.latitude
            depth = abs(origin.depth / 1e3)
            for st in streams:
                sta = st[0].stats.station
                lon2 = st[0].stats.coordinates['longitude']
                lat2 = st[0].stats.coordinates['latitude']
                dist = locations2degrees(lat1, lon1, lat2, lon2)
                tts = getTravelTimes(dist, depth)
                list_ = arrivals.setdefault(sta, [])
                for tt in tts:
                    tt['time'] = origin_time + tt['time']
                    if starttime < tt['time'] < endtime:
                        has_arrivals = True
                        list_.append(tt)
            if not has_arrivals:
                events[:] = events[:-1]
    except Exception as e:
        msg = ("Problem while fetching events or determining theoretical "
               "phases: %s: %s" % (e.__class__.__name__, str(e)))
        return None, None, msg
    return events, arrivals, None


def apply_gse2_calib(tr):
    """
    Applies GSE2 specific calibration to overall sensitivity.
    Not valid for accelerometer data!
    """
    try:
        calibration = tr.stats.calib * ((2.0 * np.pi / tr.stats.gse2.calper) ** 1) * 1e-9
        tr.stats.paz.sensitivity = tr.stats.paz.sensitivity / calibration
    except Exception as e:
        msg = ("Warning: Failed to apply GSE2 calibration factor to overall "
               "sensitivity (%s, %s). Continuing anyway.")
        msg = msg % (e.__class__.__name__, str(e))
        print msg


def map_rotated_channel_code(channel, rotation):
    """
    Modifies a channel code according to given rotation (e.g. EHN -> EHR)

    :type channel: str
    :type rotation: str
    """
    if rotation in ("LQT", "ZRT"):
        while len(channel) < 3:
            msg = ("Channel code ('%s') does not have three characters. "
                   "Filling with leading spaces.")
            warnings.warn(msg % channel)
            channel = " " + channel
        if rotation == "LQT":
            mapping = ROTATE_LQT_COMP_MAP
        elif rotation == "ZRT":
            mapping = ROTATE_ZRT_COMP_MAP
        channel = channel[0:2] + mapping[channel[2]]
    elif rotation is None:
        pass
    return channel
