# High and Low - NYC GIS Utilities

# version
appName = 'hlparser'
appInfo = 'highLow paser Tool v1.0 (mouser@donationcoder.com) [12/25/23]'

# lib imports
from lib.jr import jrfuncs
from lib.jr.jrfuncs import jrprint

# other imports
import time
import os
from datetime import datetime


# class helper
from hlparser import HlParser




# ---------------------------------------------------------------------------
# expand neighborhoods by a certain amount which helps enclose surrounding streets
# though note that this makes neighborhoods partially overlap
optionOverrides = {'basedir': os.path.dirname(os.path.abspath(__file__)), 'savedir': '$workingdir/output'}
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
def main():
    # announce app
    jrprint(appInfo)

    hlparser = HlParser('./options', optionOverrides)
    hlparser.processCommandline(appName, appInfo)

	# done
    return True
# ---------------------------------------------------------------------------














































# ---------------------------------------------------------------------------
# main stuff
if __name__ == "__main__":
    # execute only if run as a script
    startTime = time.time()
    #
    bretv = main()
    if (not bretv):
        jrprint('WARNING: Some operation failed.')
    #
    endTime = time.time()
    jrprint('')
    dtimestr = datetime.now().strftime('%A, %B %d at %I:%M %p')
    errorCount = jrfuncs.getJrPrintErrorCount()
    message = 'Finished in {} on {}'.format(jrfuncs.niceElapsedTimeStr(endTime-startTime), dtimestr)
    if (errorCount==0):
        message += ', with NO errors.'
    else:
        message += ', with {} TOTAL ERRORS!'.format(errorCount)
    jrprint(message + '.')
# ---------------------------------------------------------------------------



