import * as fs from 'fs';
import * as express from 'express';
import * as bodyParser from 'body-parser';
import {existsSync} from 'fs';
//import * as cors from 'cors';
import {exec, execSync, spawn, ChildProcess} from 'child_process';

interface Browser {
    name: string;
    lowerName: string;
    grepSearch: string;
    argumentFilter: string;
    workerName: string;
    isBrowser(userAgent: string): boolean;
}

const Browsers: Browser[] = [
    {
        name: "Chrome",
        lowerName: "chrome",
        grepSearch: "chrome\\|chromium\\|Chrome",
        argumentFilter: "--type=renderer",
        workerName: "DedicatedWorker",
        isBrowser: (userAgent: string) => userAgent.indexOf("Chrome") !== -1 || userAgent.indexOf("Chromium") !== -1
    },
    {
        name: "Firefox",
        lowerName: "firefox",
        grepSearch: "firefox",
        argumentFilter: "-contentproc",
        workerName: "DOM Worker",
        isBrowser: (userAgent: string) => userAgent.indexOf('Firefox') !== -1
    }
];

let desiredEvents = [
    'cpu-cycles', // alias for cycles
    'instructions',
    'cache-references',
    'cache-misses',
    'branch-instructions',
    'branch-misses',
    'stalled-cycles-backend',
    'stalled-cycles-frontend',
    'L1-dcache-load-misses',
    'L1-dcache-loads',
    'L1-dcache-prefetch-misses',
    'L1-dcache-prefetches',
    'L1-dcache-stores',
    'L1-icache-load-misses',
    'L1-icache-loads',
    'L1-icache-prefetches',
    'LLC-load-misses',
    'LLC-loads',
    'LLC-stores',
    'branch-load-misses',
    'branch-loads',
    'dTLB-load-misses',
    'dTLB-loads',
    'iTLB-load-misses',
    'iTLB-loads',
];

let rawEvents = [
    'r00c4', // branch instructions retired
    'r00c5', // branch misprediction retired
    'r04c5', // all branch mispredictions
    'r01c5', // conditional branch mispredictions
    'r04c4', // all branches
    'r01c4', // conditional branches
    'r08c4', // near returns
    'r01d1', // L1 load hit
    'r02d1', // L2 load hit
    'r04d1', // L3 load hit
    'r08d1', // L1 load miss
    'r10d1', // L2 load miss
    'r20d1', // L3 load miss
    'r81d0', // all loads retired
    'r82d0', // all stores retired
    'r412e', // LLC misses
    'r4f2e', // LLC references
    'r1c0',  // instructions retired
];

//let argv = process.argv.slice(2);

let events: string;

const app = express();

app.use(bodyParser.raw({ type: 'application/x-tar' }));

//app.use(cors());
app.use('/', express.static('.'));
app.use('/', express.static('app'));


let perfProcesses: ChildProcess[] = [];
function findWorkerTids(pid: number, workerName: string): number[] {
    try {
        return execSync(`ls -1 /proc/${pid}/task`).toString().trim().split("\n")
            // Remove non-numerical folders.
            .map((item) => parseInt(item, 10))
            .filter((item) => !isNaN(item))
            // Remove non-worker threads.
            .filter((item) => {
                try {
                    return execSync(`cat /proc/${pid}/task/${item}/comm`).toString().trim() === workerName;
                } catch (e) {
                    return false;
                }
            });
    } catch (e) {
        return [];
    }
}

function tryStartPerf(pid: number, binary: string, browser: Browser): ChildProcess[] {
    return findWorkerTids(pid, browser.workerName).map((tid) => {
        let nameBase: string = `perf_data/perf-${browser.name}-${binary}-${pid}-${tid}`;
        let name = `${nameBase}.data`;
        let postfix = 0;
        while (existsSync(name)) {
            name = `${nameBase}-${postfix}.data`;
            postfix++;
        }
        return spawn(
            "perf",
            ["stat",
             "-x,",
             "-e", events,
             "-t", tid.toString(),
             "-o", name,
            ],
            { stdio: 'inherit' });
    });
}

app.get('/start', function(req, res) {
    const binary = req.query.binary ? req.query.binary : "unknown";
    const userAgent = req.header('user-agent');
    const possibleBrowsers = Browsers.filter((b) => b.isBrowser(userAgent));
    if (possibleBrowsers.length === 0) {
        console.log(`Unknown browser: ${userAgent}`);
        res.status(500).send(`Unknown browser: ${userAgent}`);
        return;
    } else if (possibleBrowsers.length > 1) {
        const errMsg = `userAgent is ambiguous: ${userAgent}\nPossible browsers: ${possibleBrowsers.map((b) => b.name).join(", ")}`;
        console.log(errMsg);
        res.status(500).send(errMsg);
        return;
    }
    const browser = possibleBrowsers[0];
    console.log(`Received /start request for ${binary} in browser ${browser.name}.`);
    // Figure out PID of Chrome.
    exec(`ps -eo pid,start_time,args --sort=start_time | grep "${browser.grepSearch}"`, (err, stdout, stderr) => {
        if (err || stderr.length > 0) {
            // Internal Server Error.
            console.log(`Failed to find ${browser.name}'s PID.`);
            res.status(500).send(`Failed to find ${browser.name}'s PID.`);
        } else {
            // Filter out invalid processes
            const processes = stdout.toString().trim().split("\n").filter(
                (line) => line.indexOf(browser.argumentFilter) !== -1);
            // Desired PID should be last one in list, so search from bottom up
            for (let i = processes.length - 1; i >= 0; i--) {
                const process = processes[i].trim();
                console.log(`Trying PID: ${process.slice(0, process.indexOf(' '))}`);
                const pid = parseInt(process.slice(0, process.indexOf(' ')), 10);
                if (isNaN(pid)) {
                    res.status(500).send(`Failed to parse PID from string ${process}`);
                    return;
                }
                perfProcesses = tryStartPerf(pid, binary, browser);
                if (perfProcesses.length > 0) {
                    console.log(`Number of perf processed: ${perfProcesses.length}`);
                    res.send();
                    return;
                }
            }
            console.log(`Unable to find a suitable ${browser} process.`);
            res.status(500).send(`Failed to find a suitable ${browser} process.`);
        }
    });
});

app.get('/stop', function(req, res) {
    console.log("Received /stop request.");
    let count = perfProcesses.length;
    function exitCounter() {
        if (--count === 0) {
            perfProcesses = [];
            res.send();
            execSync('chmod -R ugo+r ./perf_data');
            execSync('chown -R bpowers:bpowers ./perf_data');
        }
    }
    perfProcesses.forEach((p) => {
        p.on('exit', exitCounter);
        p.kill('SIGINT');
    });
    setTimeout(() => {
        if (count > 0) {
            res.status(500).send(`Unable to end all perf processes.`);
        }
    }, 10000);
    if (perfProcesses.length === 0) {
        res.send();
        execSync('chmod -R ugo+r ./perf_data');
        execSync('chown -R bpowers:bpowers ./perf_data');
    }
});

app.get('/exit', function(req, res) {
    res.send();
    process.exit();
});

app.post('/record', function(req, res) {
    const userAgent = req.header('user-agent');
    const possibleBrowsers = Browsers.filter((b) => b.isBrowser(userAgent));
    if (possibleBrowsers.length === 0) {
        console.log(`Unknown browser: ${userAgent}`);
        res.status(500).send(`Unknown browser: ${userAgent}`);
        return;
    } else if (possibleBrowsers.length > 1) {
        const errMsg = `userAgent is ambiguous: ${userAgent}\nPossible browsers: ${possibleBrowsers.map((b) => b.name).join(", ")}`;
        console.log(errMsg);
        res.status(500).send(errMsg);
        return;
    }
    const browser = possibleBrowsers[0];
    const size = req.query.size;
    const benchmark = req.query.benchmark;
    const bsize = req.body.length;
    console.log(`Received /record request for ${benchmark} (size: ${size}) -- body size ${bsize}`);
    const fileName = `./results_${browser.lowerName}_${size}_${benchmark}.tar`;
    fs.writeFileSync(fileName, req.body);
    execSync('chmod -R ugo+r ' + fileName);
    execSync('chown -R bpowers:bpowers ' + fileName);
    res.send();

    //process.exit(0);
});


exec(`perf list --raw-dump`, (err, stdout, stderr) => {
    if (err || stderr.length > 0) {
        console.log('perf-list error: ' + stdout);
        return;
    }

    let lines = stdout.split('\n');
    let availableEventsList = lines.map((l) => l.split(' ')).reduce((a, b) => a.concat(b));
    let availableEvents = new Set(availableEventsList);

    let ourEvents = desiredEvents.filter((e) => availableEvents.has(e));
    let missingEvents = desiredEvents.filter((e) => !availableEvents.has(e));
    console.log('missing events:');
    console.log(missingEvents);
    ourEvents = ourEvents.concat(rawEvents);
    events = ourEvents.join(',');
    console.log(events);

    app.listen(9000, 'localhost', function() {
        console.log("Server now listening on http://localhost:9000/");
    });
});
