#!/usr/bin/env python3

# pylint: disable=unused-argument, no-value-for-parameter

from unittest import TestCase
import psij

from typing import Any, List


class TestCallbacks(TestCase):
    """Test case for callback tests."""

    def __init__(self, arg: Any) -> None:
        """Initialize test case."""
        self._cb_states: List[psij.JobState] = list()
        TestCase.__init__(self, arg)

    def state_cb(self, job: psij.Job, status: psij.JobStatus) -> None:
        """State callback."""
        self._cb_states.append(status.state)

    def test_job_callbacks(self) -> None:
        """Test :class:`psij.Job` callbacks."""
        self._cb_states = list()
        job = psij.Job(psij.JobSpec(executable='/bin/false'))
        job.set_job_status_callback(self.state_cb)
        jex = psij.JobExecutor.get_instance(name='local')
        jex.submit(job)
        job.wait()

        self.assertEqual(len(self._cb_states), 3)
        self.assertIn(psij.JobState.QUEUED, self._cb_states)
        self.assertIn(psij.JobState.ACTIVE, self._cb_states)
        self.assertIn(psij.JobState.FAILED, self._cb_states)

        self._cb_states = list()
        job = psij.Job(psij.JobSpec(executable='/bin/date'))
        job.set_job_status_callback(self.state_cb)
        jex = psij.JobExecutor.get_instance(name='local')
        jex.submit(job)
        job.wait()

        self.assertEqual(len(self._cb_states), 3)
        self.assertIn(psij.JobState.QUEUED, self._cb_states)
        self.assertIn(psij.JobState.ACTIVE, self._cb_states)
        self.assertIn(psij.JobState.COMPLETED, self._cb_states)

    def test_job_executor_callbacks(self) -> None:
        """Test :class:`psij.JobExecutor` callbacks."""
        self._cb_states = list()
        job = psij.Job(psij.JobSpec(executable='/bin/date'))
        jex = psij.JobExecutor.get_instance(name='local')
        jex.set_job_status_callback(self.state_cb)
        jex.submit(job)
        job.wait()

        self.assertEqual(len(self._cb_states), 3)
        self.assertIn(psij.JobState.QUEUED, self._cb_states)
        self.assertIn(psij.JobState.ACTIVE, self._cb_states)
        self.assertIn(psij.JobState.COMPLETED, self._cb_states)
