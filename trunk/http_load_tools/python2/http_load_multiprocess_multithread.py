#!/usr/bin/env python
#  Copyright (c) 2009 Corey Goldberg (corey@goldb.org)
#
#  Multi-Process, Multi-Thread, HTTP Load Generator


import httplib
import multiprocessing
import os
import Queue
import sys
import threading
import time
import urlparse



URL = 'http://localhost/'
PROCESSES = 3
PROCESS_THREADS = 4
INTERVAL = 0  # secs
RUN_TIME = 60  # secs
RAMPUP = 0  # secs



def main():
    q = multiprocessing.Queue()
    rw = ResultWriter(q)
    rw.setDaemon(True)
    rw.start()
    
    start_time = time.time()    
    
    for i in range(PROCESSES):
        manager = LoadManager(q, start_time, i, PROCESS_THREADS, INTERVAL, RUN_TIME, RAMPUP)
        manager.start()
    


class LoadManager(multiprocessing.Process):
    def __init__(self, queue, start_time, process_num, num_threads=1, interval=0, run_time=10, rampup=0):
        multiprocessing.Process.__init__(self)
        self.q = queue
        self.start_time = start_time
        self.process_num = process_num
        self.num_threads = num_threads
        self.interval = interval
        self.run_time = run_time
        self.rampup = rampup
        self.parsed_url = urlparse.urlsplit(URL)
        
    def run(self):
        thread_refs = []
        for i in range(self.num_threads):
            spacing = float(self.rampup) / float(self.num_threads)
            if i > 0:
                time.sleep(spacing)
            agent_thread = LoadAgent(self.q, self.parsed_url, self.interval, self.start_time, self.run_time)
            agent_thread.setDaemon(True)
            thread_refs.append(agent_thread)
            print 'starting process %i, thread %i' % (self.process_num + 1, i + 1)
            agent_thread.start()            
        for agent_thread in thread_refs:
            agent_thread.join()



class LoadAgent(threading.Thread):
    def __init__(self, queue, parsed_url, interval, start_time, run_time):
        threading.Thread.__init__(self)
        self.q = queue
        self.interval = interval
        self.start_time = start_time
        self.run_time = run_time
        self.parsed_url = parsed_url
        
        # choose timer to use
        if sys.platform.startswith('win'):
            self.default_timer = time.clock
        else:
            self.default_timer = time.time
            
    def run(self):
        while True:
            start = self.default_timer()               
            try:
                status = self.send(self.parsed_url)
            except Exception, e:
                status = 0
                print e
            finish = self.default_timer()
            latency = finish - start
            elapsed = time.time() - self.start_time 
            self.q.put((elapsed, status, latency))
            if elapsed >= self.run_time:
                break
            expire_time = self.interval - latency
            if expire_time > 0:
                time.sleep(expire_time)
           
    def send(self, parsed_url):
        if parsed_url.scheme.endswith('s'):
            conn = httplib.HTTPSConnection(parsed_url.netloc)
        else:
            conn = httplib.HTTPConnection(parsed_url.netloc)
        try:
            conn.request('GET', parsed_url.path, parsed_url.query)
            resp = conn.getresponse()
            resp.read()
        except Exception, e:
            raise Exception('Connection Error: %s' % e)
        finally:
            conn.close()
        return resp.status
    


class ResultWriter(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.q = queue
    
    def run(self):
        with open('results.csv', 'w') as f:     
            while True:
                try:
                    elapsed, status, latency = self.q.get(False)
                    f.write('%.3f,%i,%.3f\n' % (elapsed, status, latency))
                    f.flush()
                    print '%.3f' % latency
                except Queue.Empty:
                    # re-check queue for messages every x sec
                    time.sleep(.1)



if __name__ == '__main__':
    main()