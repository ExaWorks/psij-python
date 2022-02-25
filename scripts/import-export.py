import psij
from psij import Export
from psij import Import


jex = psij.JobExecutor.get_instance('slurm')

N=1 # number of jobs to run

def make_job():
    job = psij.Job()
    spec = psij.JobSpec()
    spec.executable = 'echo Hello World'
    spec.arguments = ['10']
    job.spec = spec
    return job



# Create Job and export
e = Export()
for i in range(N):
    job = make_job()
    e.export(obj=spec , dest="jobSpec." + str(i) + ".json")
    
# Import Job and submit
i = Import()
jobs = []    
for i in range(N):    
    job = psij.Job()
    spec = i.load(src="jobSpec." + str(i) + ".json")
    job.spec = spec
    jobs.append(job)
    jex.submit(job)

for i in range(N):
    jobs[i].wait()