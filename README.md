to run:

```
$ npm install
$ tsc
$ sudo node server.js
```

You shouldn't need to launch Chrome or any other browser with
additional runtime flags, as `SharedArrayBuffer` support has now
shipped.

In the browser, navigate to [localhost:9000](http://localhost:9000/).
Type `runspec` and then enter.  When it is done, You can hit the
download button, which should give a `tar` file containing the output
of the benchmarks (which can be compared against native, to ensure the
operation was correct), along with timing information.

You can check the output from the Browsix shell by:

```
$ cat /opt/SPEC_CPU2006v1.2/benchspec/CPU2006/470.lbm/run/run_base_test_browsix.0000/speccmds.out
```

And should see some spew that ends with something like:

```
running commands in speccmds.cmd 1 times
runs started at 1476221840, 35000000, Tue Oct 11 17:37:20 2016
run 1 started at 1476221840, 38000000, Tue Oct 11 17:37:20 2016
child started: 0, 1476221840, 41000000, pid=5, '../run_base_test_browsix.0000/lbm_base.browsix 20 reference.dat 0 1 100_100_130_cf_a.of'
child finished: 0, 1476221843, 508000000, sec=3, nsec=467000000, pid=5, rc=0
run 1 finished at: 1476221843, 516000000, Tue Oct 11 17:37:23 2016
run 1 elapsed time: 3, 478000000, 3.478000000
runs finished at 1476221843, 519000000, Tue Oct 11 17:37:23 2016
runs elapsed time: 3, 484000000, 3.484000000
```

Perf output will appear in `perf_data`.

KNOWN ISSUES:
-------------

- only one benchmark is currently checked in
- currently running a 'test' workload - the full workload takes more time so is more stable, but annoying to iterate fixes on.
- the tar file is empty, this is due to BrowserFS in-memory filesystem not setting an inode number.
- performance is understated, as it includes time taken to fork, exec
  a new shell, and finally exec the benchmark, which adds several
  hundred milliseconds, AND also includes time to JIT benchmark.

Perf Counter Design:
-------------------------------------

- Program triggers a sync HTTP call when it is time to start / stop performance monitoring (a `GET` to `/start` or `/stop`).
- A small HTTP server written in JavaScript receives the request.
- When HTTP server receives a request for "/start":
  - It shells out to `ps` with filtering to find all Google Chrome rendering processes
  - It uses `cat /proc/$CHROME_PID/task/**/comm` to identify the type of thread
    in a chrome process -- our benchmark process will identify itself as
    `DedicatedWorker`.
  - Then, it spawns `perf` on each `DedicatedWorker` thread that it found.
- When the HTTP server receives a request for `/stop`, it sends `SIGINT` to all perf processes.
- We should be able to similarly use perf to record CPU performance counters
  for the natively compiled benchmarks on linux.



start:
- benchmark name
- browser version

- sending tar file
