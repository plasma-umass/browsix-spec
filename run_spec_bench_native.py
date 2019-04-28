import os
import sys
import commands
import random
import shutil
import re

if (len(sys.argv) <= 1):
  print ("Specify benchmark(s)")
  sys.exit (1)

print (os.environ)

def main (n_iter):
  #spec_bench_path = "/spec/cpu2006_asmjs/benchspec/CPU2006"
  spec_bench_path = "/spec2017/cpu2006_asmjs/benchspec/CPU"
  #runcommand = "runspec" 
  runcommand = "runcpu"
  browsix_spec_path = "/mnt/homes/abhinav/ubuntu/abhinav/browsix/browsix-spec2006"
  fs_browsix_spec_path = os.path.join(browsix_spec_path, "fs")

  benchs = sys.argv[1:]
  if (benchs[0] == "ALL-2006"):
    browsix_cpu_path = os.path.join(fs_browsix_spec_path, spec_bench_path[1:])
    benchs = os.listdir (browsix_cpu_path)
    for n in ['638.imagick_s', '641.leela_s', '657.xz_s', '644.nab_s']:
      benchs.remove (n)

  elif (benchs[0] == "ALL-C"):
    browsix_cpu_path = os.path.join(fs_browsix_spec_path, spec_bench_path[1:])
    all_c = ["401.bzip2", "429.mcf", "445.gobmk", "456.hmmer", "458.sjeng", 
              "462.libquantum", "464.h264ref", "433.milc", "470.lbm",
              "482.sphinx3"]
    all_benchs = os.listdir (browsix_cpu_path)
    benchs = []
    for bench in all_benchs:
      if (bench in all_c):
        benchs += [bench]
  elif (benchs[0] == 'ALL-C++'):
    browsix_cpu_path = os.path.join(fs_browsix_spec_path, spec_bench_path[1:])
    all_cpp = ["444.namd", "447.dealII", "450.soplex", "453.povray", 
              "473.astar", "483.xalancbnk", ]
    all_benchs = os.listdir (browsix_cpu_path)
    benchs = []
    for bench in all_benchs:
      if (bench in all_cpp):
        benchs += [bench]
  elif (benchs[0] == 'ALL-2017'):
    benchs = ['641.leela_s', '644.nab_s']
  
  #benchs = ['401.bzip2']
  config = "native-perf" #"native-perf-polly" #"native-perf"  #"native-musl"
  size = "ref"

  if (sys.argv[1] == "ALL-2006"):
    print "Running for ALL benchmarks ", benchs
  else:
    print "Running for benchmarks ", benchs

  print "config = ", config, ", size = ", size

  build_dir = "build/"
  run_dir = "run/"

  for bench in benchs:
    if (bench.find('.') == -1):
      print ("Enter full name of benchmark ", bench)
      sys.exit (1)

  os.chdir ('/spec/cpu2006_asmjs')
  print (commands.getoutput ('. ./shrc'))

  bench_times = {}
  bench_with_errors = []

  found_errors = False
  s = "".join(os.listdir ("/tmp/native-perf"))
  total_func_calls = {}

  for bench in benchs:
    if (bench[bench.find(".")+1:] in s):
      print ('Not executing. perf data already exists in /tmp/native-perf')
      continue
    try:
      os.chdir (spec_bench_path)
      _build_dir = os.path.join(spec_bench_path, bench, build_dir)
      _run_dir = os.path.join(spec_bench_path, bench, run_dir)
      if (os.path.exists (_build_dir)):
        shutil.rmtree (_build_dir)
      if (os.path.exists (_run_dir)):
        shutil.rmtree (_run_dir)
      if (not os.path.exists (_build_dir)):
        os.mkdir (_build_dir)
      
      if (not os.path.exists (_run_dir)):
        os.mkdir (_run_dir)
      
      command = runcommand + " --size=%s --rebuild --tune=base --config=%s.cfg --noreportable --iterations=1 %s" % (size, config, bench)
      print "Running Command ", command
      print commands.getoutput (command)
      os.chdir (browsix_spec_path)
      _bench_run_dir = ""
      for d in os.listdir (_run_dir):
        if (d.find ("run_base") != -1):
          _bench_run_dir = d
          break

      if (size == 'ref'):
        results_dir = os.path.join ("/mnt/homes/abhinav/ubuntu/abhinav/browsix/browsix-spec2006", "native-perf-iter-%d"%n_iter)      

        if (not os.path.exists (results_dir)):
          os.mkdir (results_dir)

        for f in os.listdir ('/tmp/native-perf'):
          shutil.move (os.path.join ('/tmp/native-perf', f), results_dir + "/")

      bench_run_dir = os.path.join (_run_dir, _bench_run_dir) #There is only one directory here
      
      with open (os.path.join (bench_run_dir, 'speccmds.out'), 'r') as f:
        text = f.read ()
        q = re.findall (r"runs elapsed time:.+", text)[0]
        l = q.split(',')
        time = float(l[-1])
        print 'time to run bench %s is '%(bench), time
        bench_times[bench] = time
      
      if (config.find("gprof") != -1):
        current_dir = os.getcwd ()
        os.chdir (bench_run_dir)
        files = os.listdir (bench_run_dir)
        bench_binary = None
        for f in files:
          if (f.find (bench[bench.find(".")+1:]) == 0):
            bench_binary = f
            break
            
        assert (bench_binary != None)
        call_data = commands.getoutput ("gprof %s gmon.out"%(bench_binary))
        lines = re.findall(r'.+', call_data)
        i = 0
        while (lines[i].find ("calls")  == -1):
          i+=1
        calls = 0
        while (lines[i].find ("%") == -1):
          c = re.findall(r'[\d\.]+\s+[\d\.]+\s+[\d\.]+\s+(\d+).*', lines[i])
          if (c != []):
            calls += int(c[0])
          i+=1
        print "number of calls", calls
        total_func_calls[bench] = calls
        os.chdir (current_dir)
        
    except Exception as e:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      print "[Error%s]:"%bench, e, "at", exc_tb.tb_lineno
      found_errors = True
      bench_with_errors.append ((bench, "[Error]:] " + str(e) + " at " + str(exc_tb.tb_lineno)))


  if (found_errors):
    print ("Found Errors: Go check it")
    for b in bench_with_errors:
      print b[0], b[1]
      
  print ("Iter: %d: Benchmark and Times are:"%n_iter)
  for k in bench_times.keys ():
    print k, bench_times[k]

  print ("Number of Function calls:")
  for k in total_func_calls.keys ():
    print k, total_func_calls[k]

for i in range (1, 6):
  main (i)