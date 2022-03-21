import psij

jex = psij.JobExecutor.get_instance('slurm')

N=2 # number of jobs to run

def make_job(i):
    job = psij.Job()
    spec = psij.JobSpec()
    spec.executable = 'echo'
    spec.arguments = ['I am number ' , i , ">>" , "hello.txt"]
    spec.stdout_path = 'hello.' + str(i) + '.stdout'
    job.spec = spec
    return job

jobs = []
for i in range(N):
    job = make_job(i)
    jobs.append(job)
    jex.submit(job)

for i in range(N):
    jobs[i].wait()