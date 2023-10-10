import sys

from psij import Job, JobExecutor, JobState


def attach() -> None:
    ex = JobExecutor.get_instance('local')
    native_id = sys.stdin.read().strip()
    job = Job()
    ex.attach(job, native_id)
    # The status may not be updated immediately after the attach() call, so
    # we wait until we get a non-NEW status.
    status = job.wait(target_states=[JobState.QUEUED, JobState.ACTIVE, JobState.COMPLETED])
    print(status)


if __name__ == '__main__':
    attach()
