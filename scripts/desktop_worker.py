"""Windows process adapter for EduNova desktop AI, memory and export queues.

Reuse RQ job/state handling and Windows Job Objects for process lifetime.
This does not sandbox user code. Desktop services own a private Redis instance.
Scheduled jobs are not used by the current application queue producers.
"""
import os
from pathlib import Path
import subprocess
import sys
import time

import win32api
import win32con
import win32job
from redis import Redis
from rq import Queue, SimpleWorker, Worker
from rq.command import parse_payload
from rq.executions import Execution
from rq.exceptions import StopRequested
from rq.job import Job, JobStatus
from rq.worker import WorkerStatus
from rq.utils import now


class WindowsDesktopWorker(Worker):
    """Keep application queue semantics; adapt the Windows process lifecycle."""

    def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
        # RQ's POSIX signal interrupts its blocking dequeue. On Windows the
        # cooperative stop flag needs a bounded wait and a loop checkpoint.
        self._windows_waiting_for_job = True
        try:
            return super().dequeue_job_and_maintain_ttl(
                min(timeout, 1) if timeout is not None else None, max_idle_time
            )
        finally:
            self._windows_waiting_for_job = False

    def heartbeat(self, *args, **kwargs):
        if getattr(self, "_windows_waiting_for_job", False) and self._stop_requested:
            raise StopRequested()
        return super().heartbeat(*args, **kwargs)

    def handle_payload(self, message):
        if parse_payload(message).get("command") == "shutdown":
            # RQ's os.kill(pid, SIGINT) terminates a Windows process rather
            # than delivering the POSIX warm-shutdown signal. Request that
            # the existing worker loop exit after its current job instead.
            self._shutdown_requested_date = now()
            self._stop_requested = True
            self.set_shutdown_requested_date()
            self.handle_warm_shutdown_request()
            return
        super().handle_payload(message)

    def kill_horse(self, sig=None):
        handle = getattr(self, "_job_handle", None)
        if handle is not None:
            win32job.TerminateJobObject(handle, 137)

    def execute_job(self, job, queue):
        self.prepare_execution(job)
        self._job_handle = win32job.CreateJobObject(None, "")
        limits = win32job.QueryInformationJobObject(self._job_handle, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(self._job_handle, win32job.JobObjectExtendedLimitInformation, limits)
        process = None
        reason = None
        try:
            process = subprocess.Popen(
                [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
                 "horse", self.name, queue.name, job.id, self.execution.id],
                stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Child waits on stdin before touching the job, so it cannot spawn
            # untracked descendants before its Windows Job Object is assigned.
            ph = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, process.pid)
            try:
                win32job.AssignProcessToJobObject(self._job_handle, ph)
            finally:
                ph.Close()
            self._horse_pid = process.pid
            process.stdin.write(b"1")
            process.stdin.close()
            began = time.monotonic()
            last_beat = began
            # The desktop wall-clock limit includes interpreter startup and
            # callbacks, preventing native calls from defeating RQ timers.
            deadline = began + job.timeout if job.timeout and job.timeout > 0 else float("inf")
            while process.poll() is None:
                current = time.monotonic()
                if current >= deadline:
                    reason = "Windows desktop supervisor: hard timeout"
                    self.kill_horse()
                    break
                if current - last_beat >= 0.5 and job.get_status(refresh=True) == JobStatus.STARTED:
                    self.set_current_job_working_time(current - began)
                    self.maintain_heartbeats(job)
                    last_beat = current
                time.sleep(0.025)
            process.wait(timeout=5)
            if process.returncode == 0:
                # perform_job owns all normal transitions, including queued
                # or scheduled retries and result_ttl=0 deletion. Do not
                # classify those transitions as an abnormal child exit.
                return
            job.refresh()
            if job.get_status(refresh=True) not in (JobStatus.FINISHED, JobStatus.FAILED, JobStatus.STOPPED):
                job.ended_at = now()
                if self._stopped_job_id == job.id and job.stopped_callback:
                    job.execute_stopped_callback(self.death_penalty_class)
                self.handle_job_failure(job, queue, exc_string=reason or f"Windows desktop child exited {process.returncode}")
        finally:
            # Closing the last handle also kills descendants when the parent
            # itself is terminated unexpectedly. This is lifecycle control,
            # not a filesystem/network sandbox for untrusted code.
            self._job_handle.Close()
            self._job_handle = None
            if process is not None:
                process.wait(timeout=5)
            self._horse_pid = 0
            self.set_current_job_working_time(0)
            self.set_state(WorkerStatus.IDLE)


def main():
    connection = Redis.from_url(os.environ["REDIS_URL"])
    if sys.argv[1] == "horse":
        if sys.stdin.buffer.read(1) != b"1":
            raise SystemExit(2)
        _, _, worker_name, queue_name, job_id, execution_id = sys.argv
        worker = SimpleWorker([queue_name], connection=connection, name=worker_name, prepare_for_work=False)
        job = Job.fetch(job_id, connection=connection)
        worker.execution = Execution.fetch(execution_id, job_id, connection=connection)
        worker._is_horse = True
        worker.perform_job(job, Queue(queue_name, connection=connection))
    else:
        import argparse

        parser = argparse.ArgumentParser(description="EduNova Windows queue worker")
        parser.add_argument("mode", choices=["worker"])
        parser.add_argument("queues", nargs="+")
        parser.add_argument("--burst", action="store_true")
        args = parser.parse_args()
        WindowsDesktopWorker(args.queues, connection=connection, job_monitoring_interval=1).work(
            burst=args.burst, with_scheduler=False, logging_level="WARNING")


if __name__ == "__main__":
    main()
