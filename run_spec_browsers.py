#!/usr/bin/env python3

import traceback
import delegator
import os
import shutil
import signal
import sys
import time

from os import path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options as FFOptions
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import ast
import re

print ("== Make Sure You use node 8.x ==")

MAX_TIMEOUT = 2 * 60 * 60 # 2 hour

BENCHMARKS = 'bzip2 mcf milc namd gobmk soplex povray sjeng libquantum h264ref lbm astar sphinx3 leela_s nab_s'.split()
#BENCHMARKS = 'mcf'.split ()
#BENCHMARKS = 'mcf'.split()[:1]
#BENCHMARKS = ['libquantum']

SIZE = 'ref'

CWD = path.abspath(os.getcwd())

SPEC_DIR = '/spec/cpu2006_asmjs'

CMP_PATH = path.join(CWD, 'hostbin', 'cmp')
CLEAN_PATH = path.join(CWD, 'hostbin', 'clean')
UNPACK_PATH = path.join(CWD, 'hostbin', 'unpack')
SERVER_JS = path.join(CWD, 'server.js')
SERVER_PATH = 'node {}'.format('server.js')


def get_firefox():
    binary = FirefoxBinary('/usr/bin/firefox')
    fp = webdriver.FirefoxProfile ()
    fp.DEFAULT_PREFERENCES['frozen']['javascript.options.shared_memory'] = True
    fp.DEFAULT_PREFERENCES['frozen']['javascript.options.wasm_baselinejit'] = False
    fp.DEFAULT_PREFERENCES['frozen']['javascript.options.wasm'] = True
    fp.DEFAULT_PREFERENCES['frozen']['javascript.options.wasm_ionjit'] = True
    fp.DEFAULT_PREFERENCES['frozen']['browser.tabs.remote.autostart'] = False
    fp.DEFAULT_PREFERENCES['frozen']['devtools.console.stdout.content'] = True
    options = FFOptions ()
    fp.set_preference("browser.download.folderList", 2)
    fp.set_preference("browser.download.dir", "/mnt/homes/abhinav/Downloads")
    fp.set_preference("browser.download.useDownloadDir", True)
    fp.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-tar")
    fp.add_extension('webconsoletap-1.0-fx.xpi')
    options.profile=fp
    options.binary = '/usr/bin/firefox'
    options.add_argument('-contentproc=2')
    d = DesiredCapabilities.FIREFOX
    d['loggingPrefs'] = {'browser' : 'ALL'}
    options.set_capability (name='loggingPrefs', value={'browser' : 'ALL'})
    return webdriver.Firefox(executable_path='/usr/bin/geckodriver', firefox_options=options, capabilities=d)


def get_chrome():
    options = Options()
    options.binary_location = '/usr/bin/google-chrome-stable'
    options.add_argument('--js_flags="--harmony-sharedarraybuffer"')
    d = DesiredCapabilities.CHROME
    d['loggingPrefs'] = {'browser' : 'ALL'}
    options.set_capability (name='loggingPrefs', value={'browser' : 'ALL'})
    return webdriver.Chrome('/usr/bin/chromedriver', chrome_options=options)


BROWSERS = {
    'chrome': get_chrome,
    #'firefox': get_firefox,
}


def run(browser, benchmark):
    # ensure we're in the directory we started
    os.chdir(CWD)

    c = delegator.run(SERVER_PATH, block=False)
    url = 'http://localhost:9000/?size={}&benchmark={}'.format(SIZE, benchmark)

    driver = BROWSERS[browser]()
    driver.get(url)

    #assert 'Browsix' in driver.title
    total_syscall_time = 0

    try:
        time.sleep(.1)
        element = WebDriverWait(driver, MAX_TIMEOUT).until(
            EC.text_to_be_present_in_element((By.ID, 'completion'), 'DONE')
        )
        a = driver.find_elements_by_id("dl-button")
        print (a)
        a[0].click()
        if (False and browser == 'firefox'):
            driver.execute_script ("window.console.requestDump()")
            tries = 100
            console_log = None
            #while (console_log == None and tries > 0) :
            console_log = driver.execute_script ("return window.console.getDump();")
            tries = tries - 1
            print (console_log)
        else:
            #Since Firefox does not support Selenium's API to get console.log messages
            #We need to use Chrome to get Time spent in Browsix numbers
            for entry in driver.get_log('browser'):
                entry_dict = ast.literal_eval(str(entry))
                if 'message' in entry_dict:
                    message = entry_dict['message']
                    syscall_time = re.findall (r'Time spent in System Calls:\s*([\d\.]+).+', message)
                    if (syscall_time != []):
                        total_syscall_time += float(syscall_time[0])

    except Exception as e:
        print ("Error executing " + benchmark)
        traceback.print_exc ()
    finally:

        time.sleep(60)

        driver.quit()

    try:
        c.terminate()
    except Exception as e:
        #print('ERROR: c.kill: {}'.format(e))
        pass
    finally:
        c.block()

    return total_syscall_time


def results_correct(browser, benchmark):
    return True
    os.chdir(SPEC_DIR)
    c = delegator.run([CLEAN_PATH, '-size=' + SIZE, '-benchmark=' + benchmark])
    if c.return_code != 0:
        print('ERROR: clean {}/{}:\n{}\n{}'.format(browser, benchmark, c.out, c.err))
        return False

    c = delegator.run([CMP_PATH, '-size=' + SIZE, '-benchmark=' + benchmark])
    if c.return_code == 0:
        print('ERROR: cmp1 {}/{}:\n{}\n{}'.format(browser, benchmark, c.out, c.err))
        return False

    c = delegator.run([UNPACK_PATH, path.join(CWD, 'results_{}_{}_{}.tar'.format(browser, SIZE, benchmark))])
    if c.return_code != 0:
        print('ERROR: unpack {}/{}:\n{}\n{}'.format(browser, benchmark, c.out, c.err))
        return False

    c = delegator.run([CMP_PATH, '-size=' + SIZE, '-benchmark=' + benchmark])
    if c.return_code != 0:
        print('ERROR: cmp2 {}/{}:\n{}\n{}'.format(browser, benchmark, c.out, c.err))
        return False

    return True


def main():
    syscall_times_f = open ('syscall-times.csv', 'a')
    syscall_times_f.write ('Benchmark Iteration BrowsixTime\n')
    syscall_times_f.close ()

    for iter in range (1, 6):
        for browser in BROWSERS:
            for benchmark in BENCHMARKS:
                print('testing {}/{}'.format(browser,benchmark))
                time.sleep(2)
                sys_call_time = run(browser, benchmark)
                syscall_times_f = open ('syscall-times.csv', 'a')
                syscall_times_f.write (benchmark + " " + str(iter) + " " + str(sys_call_time) + "\n")
                syscall_times_f.close ()
                if not results_correct(browser, benchmark):
                    print('ERROR: result incorrect for {}/{}, not recording'.format(browser, benchmark))
                    for f in os.listdir(path.join(CWD, 'perf_data')):
                        os.remove(path.join(CWD, 'perf_data', f))
                    continue
                print('\tOK: recording')
                os.chdir(CWD)
                #if (not os.path.exists (path.join(CWD, 'perf_data_valid-'+browser))):
                #    os.mkdir (path.join(CWD, 'perf_data_valid-'+browser))
                if (True):
                    if (not os.path.exists (path.join(CWD, 'perf_data_valid-iter-'+str(iter)))):
                        os.mkdir (path.join(CWD, 'perf_data_valid-iter-'+str(iter)))

                    for f in os.listdir(path.join(CWD, 'perf_data')):
                        shutil.move(path.join(CWD, 'perf_data', f), path.join(CWD, 'perf_data_valid-iter-'+str(iter)+"/"))

            if (browser == 'chrome'):
                if (True):
                    if (not os.path.exists (path.join (CWD,'spec-results-iter-'+str(iter) + '-Chrome'))):
                        os.mkdir (path.join (CWD,'spec-results-iter-'+str(iter) + '-Chrome'))

                    for f in os.listdir ("/mnt/homes/abhinav/"):
                        if f.find ("results-") == 0:
                            shutil.move (os.path.join ("/mnt/homes/abhinav/", f),
                                        path.join (CWD,'spec-results-iter-'+str(iter) + '-Chrome/',f))
            else:
                if (not os.path.exists (path.join (CWD,'spec-results-iter-'+str(iter) + '-Firefox'))):
                    os.mkdir (path.join (CWD,'spec-results-iter-'+str(iter) + '-Firefox'))

                for f in os.listdir ("/mnt/homes/abhinav/Downloads"):
                    if f.find ("results-") == 0:
                        shutil.move (os.path.join ("/mnt/homes/abhinav/Downloads", f),
                                    path.join (CWD,'spec-results-iter-'+str(iter) + '-Firefox/',f))

    return 0

if __name__ == '__main__':
    sys.exit(main())
