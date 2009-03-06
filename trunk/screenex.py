#!/usr/bin/python

from screenex_lib import *
from time import sleep

################
home_config = '~/.screenex/auth.xml.conf'
sys_config = '/etc/screenex/global.xml.conf'
################

if __name__ == "__main__":
    try:
        lib_main(home_config, sys_config)
    except (CredsError, StatementError, ConfError), e:
        print "*** Exception!!! ***\n%s\n\n" % str(e)
        "\nWait 5 secs...." 
        sleep(5)
    except KeyboardInterrupt, e:
        ename = e.__class__.__name__
        print "*** Generic Exception!!! ***\n%s\n\n" % ename 
        "\nWait 5 secs...." 
        sleep(5)