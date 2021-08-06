import psij


N = 4
M = 2


def test_submit_and_wait_for_n_jobs() -> None:
    jex = psij.JobExecutor.get_instance('local')

    def make_job() -> psij.Job:
        job = psij.Job()
        spec = psij.JobSpec()
        spec.executable = '/bin/sleep'
        spec.arguments = ['1']
        job.spec = spec
        return job

    jobs = []
    for i in range(N):
        job = make_job()
        jobs.append(job)
        jex.submit(job)

    for i in range(N):
        jobs[i].wait()


def test_run_n_throttle_m() -> None:
    class ThrottledSubmitter:
        def __init__(self) -> None:
            self.jex = psij.JobExecutor.get_instance('local', '>= 0.0.1')
            # keep track of completed jobs so that we can submit the rest
            self.jex.set_job_status_callback(self.callback)
            self.count = 0

        def make_job(self) -> psij.Job:
            job = psij.Job()
            spec = psij.JobSpec()
            spec.executable = '/bin/sleep'
            spec.arguments = ['1']
            job.spec = spec
            return job

        def submit_next(self) -> None:
            if self.count < N:
                self.jex.submit(self.jobs[self.count])
                self.count += 1

        def start(self) -> None:
            # create list of jobs
            self.jobs = [self.make_job() for i in range(N)]

            # submit initial M jobs
            while self.count < M:
                self.submit_next()

        def callback(self, job: psij.Job, status: psij.JobStatus) -> None:
            if status.final:
                # a previously submitted job is now done, we have room to
                # submit another
                self.submit_next()

    ThrottledSubmitter().start()
