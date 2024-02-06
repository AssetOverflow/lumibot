import queue
from queue import Queue
from threading import Thread


class CustomStream:

    def __init__(self):
        self._queue = Queue(1)
        self._actions_mapping = {}

    def dispatch(self, event, **payload):
        self._queue.put((event, payload))
        self._queue.join()

    def add_action(self, event_name):
        def add_event_action(f):
            self._actions_mapping[event_name] = f
            return f

        return add_event_action

    def _run(self):
        while True:
            event, payload = self._queue.get()  # This is a blocking operation.
            self._process_queue_event(event, payload)
            self._queue.task_done()

    def _process_queue_event(self, event, payload):
        if payload is None:
            payload = {}
        if event in self._actions_mapping:
            action = self._actions_mapping[event]
            action(**payload)

    def run(self, name):
        # Threads are spawned by the broker._launch_stream() code
        self._run()


class PollingStream(CustomStream):
    """
    A stream that polls an API endpoint at a regular interval and dispatches events based on the response. It is
    required that a polling action is registered with the stream using add_action(). The polling action should make a
    request to the API and dispatch events based on the response. A user can also dispatch events to the stream manually
    using dispatch(), including the poll event to force an off-cycle poll action to occur.
    """
    POLL_EVENT = "poll"

    def __init__(self, polling_interval=5.0):
        """
        Parameters
        ----------
        polling_interval: float
            Number of seconds to wait between polling the API.
        """
        super().__init__()
        self.polling_interval = polling_interval

    def _run(self):
        while True:
            try:
                # This is a blocking operation until an item is available in the queue or the timeout is reached.
                event, payload = self._queue.get(timeout=self.polling_interval)
                self._process_queue_event(event, payload)
                self._queue.task_done()
            except queue.Empty:
                # If the queue is empty, it means the polling interval has been reached.
                self._poll()
                continue

    def _poll(self):
        if self.POLL_EVENT not in self._actions_mapping:
            raise ValueError("No action is defined for the poll event. You must register a polling action with "
                             "add_action()")
        self._process_queue_event(self.POLL_EVENT, {})
