import psij

jex = psij.JobExecutor.get_instance('slurm')

N=1 # number of jobs to run

def make_job():
    job = psij.Job()
    spec = psij.JobSpec()
    
    spec.executable = 'echo'
    spec.arguments = ['HELLO WORLD!']
    
    # set project name if no default is specified
    # spec.attributes.project_name = <PROJECT_NAME>
    
    # set queue if no default is specified
    # spec.attributes.queue_name = <QUEUE_NAME>
  
    spec.stdout_path = "out.txt"
    
    # set node count
    # resource = psij.ResourceSpecV1()
    # resource.node_count = N
    
    job.spec = spec
    return job

jobs = []
for i in range(N):
    job = make_job()
    jobs.append(job)
    jex.submit(job)

for i in range(N):
    jobs[i].wait()

