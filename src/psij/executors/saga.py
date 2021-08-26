import atexit
import logging
from threading import RLock
from typing import Optional, Dict, List

from distutils.version import StrictVersion

import radical.saga as rs
import radical.saga.job.constants as ct
import time

from psij import JobExecutor, JobExecutorConfig, JobState, JobStatus, Job, \
    SubmitException, InvalidJobException

logger = logging.getLogger(__name__)


# map SAGA states to jpsi states.
_STATE_MAP = {
    rs.job.NEW: JobState.NEW,
    rs.job.PENDING: JobState.QUEUED,
    rs.job.RUNNING: JobState.ACTIVE,
    rs.job.DONE: JobState.COMPLETED,
    rs.job.FAILED: JobState.FAILED,
    rs.job.CANCELED: JobState.CANCELED,
}


class _JobMapping:
    def __init__(self, jpsi_job: Job, saga_job: Optional[rs.job.Job] = None):
        self.jpsi_job = jpsi_job
        self.saga_job = saga_job


class SagaExecutor(JobExecutor):
    """
    An executor that use SAGA to run jobs.

    For details about SAGA, see https://en.wikipedia.org/wiki/Simple_API_for_Grid_Applications
    and related links.
    """

    _NAME_ = 'saga'
    _VERSION_ = StrictVersion('0.0.1')

    def __init__(self, url: Optional[str] = None,
                 config: Optional[JobExecutorConfig] = None) -> None:
        """
        Initializes a `SagaExecutor`.

        Parameters
        ----------
        url
            An URL representing a SAGA resource manager to connect to.
        config
            Not used.
        """
        super().__init__(url=url, config=config)

        self._jobs = dict()  # type: Dict[str, _JobMapping]
        self._lock = RLock()

        self._js = None
        self._js = rs.job.Service(self.url)
        self._cb = None
        atexit.register(self._close)

    def _close(self) -> None:
        if self._js:
            self._js.close()
            self._js = None

    def __del__(self) -> None:
        """
        Removes process shutdown hooks added earlier.

        The hooks are used to close the SAGA service used by this executor.
        """
        atexit.unregister(self._close)
        self._close()

    def _state_cb(self, saga_job: rs.job.Job, metric: object, ctx: object) -> bool:
        jpsi_ids = list()
        with self._lock:
            for job_mapping in self._jobs.values():
                if job_mapping.saga_job and job_mapping.saga_job.id == saga_job.id:
                    jpsi_ids.append(job_mapping.jpsi_job.id)

        for jpsi_id in jpsi_ids:
            jpsi_job = self._get_jpsi_job(jpsi_id)
            ec = None

            print('%s: %s - %s' % (jpsi_job.id, saga_job.state, saga_job.id))
            if not jpsi_job._native_id:
                jpsi_job._native_id = saga_job.id

            if saga_job.state in [rs.FAILED, rs.DONE]:
                ec = saga_job.exit_code

            logger.debug('%s --> %s', jpsi_id, saga_job.state)

            job_status = JobStatus(_STATE_MAP[saga_job.state], time.time(), exit_code=ec)
            jpsi_job._set_status(job_status, self)
            if self._cb:
                self._cb.job_status_changed(jpsi_job, job_status)

        return True

    def submit(self, job: Job) -> None:
        """
        Submits the specified :class:`~psij.Job` to be run using SAGA.

        Parameters
        ----------
        job
            The :class:`~psij.Job` to be submitted.
        """

        assert(self._js)
        # derive SAGA job description and submit it
        job_mapping = _JobMapping(job)
        with self._lock:
            self._jobs[job.id] = job_mapping
        job._executor = self

        jd = self._job_2_descr(job)
        saga_job = self._js.create_job(jd)

        job_mapping.saga_job = saga_job
        saga_job.add_callback(rs.STATE, self._state_cb)

        # TODO: the backend attribute is not standard; why do we need it?
        self._update_job_status(job, JobStatus(JobState.QUEUED, metadata={'backend': self.url}))

        saga_job.run()

    def _get_saga_job(self, uid: str) -> rs.job.Job:
        with self._lock:
            return self._jobs[uid].saga_job

    def _get_jpsi_job(self, uid: str) -> Job:
        with self._lock:
            return self._jobs[uid].jpsi_job

    def list(self) -> List[str]:
        """
        Retrieves a list of native IDs corresponding to jobs known to this executor.

        This method does not query the SAGA backend or any of the backends behind SAGA for jobs
        not submitted through this executor. Furthermore, it simply returns the PSI-J job IDs of
        the jobs rather than native IDs.
        Returns
        -------
        A list of job IDs.
        """
        with self._lock:
            return list(self._jobs.keys())

    def attach(self, job: Job, native_id: str) -> None:
        """
        Attaches a job to a backend job.

        This method does not quite do what it is meant to do at this time.

        Parameters
        ----------
        job
            The job to attach.
        native_id
            A PSI-J job ID

        """

        saga_job = None
        with self._lock:
            # try to find job in known jobs
            for job_mapping in self._jobs.values():
                if job_mapping.jpsi_job.status.metadata:
                    job_native_id = job_mapping.jpsi_job.status.metadata.get('native_id')
                    if not job_native_id:
                        continue
                    if job_native_id == native_id:
                        saga_job = job_mapping.saga_job
                        if not saga_job:
                            continue
                        # found the native saga job, attach it to this job
                        job_mapping = _JobMapping(job, saga_job)
                        self._jobs[job.id] = job_mapping
                        break

            # saga job is not known to this executor - re-connect via backend:
            try:
                assert(self._js)
                saga_job = self._js.get_job(native_id)
                job_mapping = _JobMapping(job, saga_job)
                self._jobs[job.id] = job_mapping
            except Exception:
                pass

        if not saga_job:
            # TODO: There is a discussion on the suitability of cancel()
            #       throwing a SubmitException - same applies here
            raise SubmitException('Unknown native id: "{}'.format(native_id))

        # we found the job and reconnected to it - update the job state
        job._native_id = native_id
        state = _STATE_MAP[saga_job.state]
        if state.final:
            self._update_job_status(job, JobStatus(state, exit_code=saga_job.exit_code))
        else:
            self._update_job_status(job, JobStatus(state))

    def _job_2_descr(self, job: Job) -> rs.job.Description:
        spec = job.spec
        if not spec:
            raise InvalidJobException('Missing specification.')

        jd = rs.job.Description()
        if spec.executable:
            jd.set_attribute(ct.EXECUTABLE, spec.executable)
        if spec.arguments:
            jd.set_attribute(ct.ARGUMENTS, spec.arguments)
        if spec.environment:
            jd.set_attribute(ct.ENVIRONMENT, spec.environment)
        if spec.stdin_path:
            jd.set_attribute(ct.INPUT, spec.stdin_path)
        if spec.stdout_path:
            jd.set_attribute(ct.OUTPUT, spec.stdout_path)
        if spec.stderr_path:
            jd.set_attribute(ct.ERROR, spec.stderr_path)
        if spec.directory:
            jd.set_attribute(ct.WORKING_DIRECTORY, spec.directory)

        return jd

    def cancel(self, job: Job) -> None:
        """
        Cancels a job.

        Parameters
        ----------
        job
            The job to cancel.
        """
        saga_job = self._get_saga_job(job.id)

        if saga_job.state not in rs.FINAL:
            saga_job.cancel()


__PSI_J_EXECUTORS__ = [SagaExecutor]
