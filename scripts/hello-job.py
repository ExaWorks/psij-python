import psij

jex = psij.JobExecutor.get_instance('slurm')

N=1 # number of jobs to run

def make_job():
    job = psij.Job()
    spec = psij.JobSpec()
    spec.executable = 'echo Hello World'
    spec.arguments = ['10']
    job.spec = spec
    return job

jobs = []
for i in range(N):
    job = make_job()
    jobs.append(job)
    jex.submit(job)

for i in range(N):
    jobs[i].wait()