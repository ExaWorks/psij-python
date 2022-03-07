#! /usr/bin/python3

import psij
from psij import JobExecutor
from psij import JobSpec
import sys
import os
import argparse
from psij import Import




parser = argparse.ArgumentParser(prog='psij-consol')
subparser = parser.add_subparsers(dest="command", help='Subcommands')
validate_parser = subparser.add_parser("validate", help='validate JobSpec file')
validate_parser.add_argument("file", help="JobSpec file")
execute_parser = subparser.add_parser("run", help='execute JobSpec file')
execute_parser.add_argument("file", help="JobSpec file")
execute_parser.add_argument("-j", 
                            "--job-executor",
                            dest = "executor",
                            choices = ["cobalt"
                                       , "local"
                                       , "batch-test"
                                       , "flux"
                                       , "lsf"
                                       , "rp"
                                       , "saga"
                                       , "slurm"],
                            )
execute_parser.add_argument("-n", 
                            "--number-of-jobs",
                            dest = "jobs",
                            type = int,
                            default=1,
                            help="Number of jobs to submit"
                            )

parser.add_argument("-v", "--verbose",
                    dest = "verbose",
                    default=False,
                    action='store_true',
                    help="print detailed information")

parser.add_argument("--debug",
                    dest = "debug",
                    action='store_true',
                    help="print debug information")


# parser.print_help()    

args = parser.parse_args()

i = Import()

if args.command == 'validate':
    print("Validating " + args.file)
    job_spec = i.load(args.file)
    
    if job_spec and  isinstance(job_spec, JobSpec):
        print("File ok")
    else:
        sys.exit("Not a valid file, could not import " + args.file)
else:
    
    if not args.executor:
        sys.exit("Missing argument executor")
    
    print("Importing " + args.file)
    job_spec = i.load(args.file)
    if not (job_spec and  isinstance(job_spec, JobSpec)):
        sys.exit("Something wrong with JobSpec")
        
        
    print("Initializing job executor")
    jex = psij.JobExecutor.get_instance(args.executor)
    if not (jex and isinstance(jex, JobExecutor)):
        sys.exit("Panic, can't initialize " + args.executor)    
        
        
    number_of_jobs = args.jobs
    print("Submitting " + str(number_of_jobs) + " job(s)")
    
    jobs = [] # list of created jobs
    for i in range(number_of_jobs):
        job = psij.Job()
        job.spec = job_spec
        jobs.append(job)
        jex.submit(job)
    
    print("Waiting for jobs to finish")
    for i in range(number_of_jobs):
        jobs[i].wait()